"use client";

import { Check, Luggage, X } from "lucide-react";
import { useState } from "react";

import {
  Button,
  Checkbox,
  type Column,
  DataTable,
  Details,
  Drawer,
  EnumPill,
  Field,
  fieldErrors,
  FieldRow,
  FormError,
  Input,
  PageHeader,
  Pagination,
  Panel,
  Segmented,
  Select,
  Skeleton,
  Textarea,
} from "@/components/ui";
import type { Leave, LeaveCreate, Me } from "@/lib/api/types";
import { daysBetween, formatDateTime, formatRange, timeAgo, todayISO } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { can, isStaff } from "@/lib/permissions";
import { useDecideLeave, useLeave, useMe, useRequestLeave } from "@/lib/queries";
import { toast } from "@/lib/store";

const PAGE = 10;

function nights(l: Leave): string {
  const d = daysBetween(l.from_date, l.to_date);
  return `${d} ${d === 1 ? "day" : "days"}`;
}

function RequestForm() {
  const request = useRequestLeave();
  const blank = { leave_type: "HOME_VISIT", from_date: "", to_date: "", destination: "", reason: "", guardian_consent: false };
  const [form, setForm] = useState(blank);
  const [touched, setTouched] = useState(false);
  const errors = fieldErrors(request.error);
  const invalidRange = form.from_date && form.to_date && form.to_date < form.from_date;
  const set = (patch: Partial<typeof form>) => setForm((f) => ({ ...f, ...patch }));

  return (
    <Panel title="Request leave" description="Ask before you travel. The warden decides, and you'll be notified.">
      <form
        className="space-y-4"
        noValidate
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (!form.from_date || !form.to_date || invalidRange || form.reason.trim().length < 5) return;
          request.mutate(
            {
              ...form,
              leave_type: form.leave_type as LeaveCreate["leave_type"],
              destination: form.destination.trim() || null,
              reason: form.reason.trim(),
            },
            {
              onSuccess: () => {
                setForm(blank);
                setTouched(false);
                toast.success("Leave requested", "The warden will review it.");
              },
            },
          );
        }}
      >
        <Field label="Reason for leave" htmlFor="leave-type">
          <Select id="leave-type" value={form.leave_type} onChange={(e) => set({ leave_type: e.target.value })}>
            {OPTIONS.leaveType.map((t) => (
              <option key={t} value={t}>
                {label(t)}
              </option>
            ))}
          </Select>
        </Field>
        <FieldRow>
          <Field label="From" htmlFor="leave-from" required error={touched && !form.from_date ? "Choose the first day." : errors.from_date}>
            <Input
              id="leave-from"
              type="date"
              min={todayISO()}
              value={form.from_date}
              invalid={touched && !form.from_date}
              onChange={(e) => set({ from_date: e.target.value })}
            />
          </Field>
          <Field
            label="To"
            htmlFor="leave-to"
            required
            error={
              touched && !form.to_date
                ? "Choose the last day."
                : invalidRange
                  ? "The last day can't be before the first."
                  : errors.to_date
            }
          >
            <Input
              id="leave-to"
              type="date"
              min={form.from_date || todayISO()}
              value={form.to_date}
              invalid={(touched && !form.to_date) || !!invalidRange}
              onChange={(e) => set({ to_date: e.target.value })}
            />
          </Field>
        </FieldRow>
        <Field label="Where you'll be" htmlFor="leave-destination" help="Optional, but it helps in an emergency.">
          <Input
            id="leave-destination"
            maxLength={200}
            value={form.destination}
            onChange={(e) => set({ destination: e.target.value })}
            placeholder="Home, Syangja"
          />
        </Field>
        <Field
          label="Details"
          htmlFor="leave-reason"
          required
          error={touched && form.reason.trim().length < 5 ? "Add a few words about why." : errors.reason}
        >
          <Textarea
            id="leave-reason"
            rows={3}
            maxLength={2000}
            value={form.reason}
            invalid={touched && form.reason.trim().length < 5}
            onChange={(e) => set({ reason: e.target.value })}
          />
        </Field>
        <Checkbox
          checked={form.guardian_consent}
          onChange={(e) => set({ guardian_consent: e.target.checked })}
          label="My guardian knows and agrees"
        />
        <FormError error={request.error} />
        <Button type="submit" variant="primary" icon={Luggage} loading={request.isPending}>
          Request leave
        </Button>
      </form>
    </Panel>
  );
}

function ResidentLeave() {
  const [offset, setOffset] = useState(0);
  const list = useLeave({ limit: PAGE, offset });
  const columns: Column<Leave>[] = [
    { key: "type", header: "Leave", cell: (l) => <span className="text-snow">{label(l.leave_type)}</span> },
    {
      key: "dates",
      header: "Dates",
      cell: (l) => (
        <span className="whitespace-nowrap text-snow">
          {formatRange(l.from_date, l.to_date)}
          <span className="block text-small text-stone">{nights(l)}</span>
        </span>
      ),
    },
    { key: "status", header: "Status", cell: (l) => <EnumPill domain="leaveStatus" value={l.status} /> },
    {
      key: "note",
      header: "Warden's note",
      hideBelow: "md",
      cell: (l) => <span className="line-clamp-2 text-mist">{l.decision_note ?? "—"}</span>,
    },
  ];
  return (
    <>
      <PageHeader title="Leave" description="Request leave before you travel and follow the warden's decision." />
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <RequestForm />
        <Panel title="Your requests" flush>
          <DataTable
            columns={columns}
            rows={list.data?.items}
            rowKey={(l) => l.id}
            loading={list.isFetching}
            error={list.error}
            onRetry={() => list.refetch()}
            empty={{ icon: Luggage, title: "No leave requested yet", description: "Requests you make appear here with the decision." }}
            footer={
              list.data && list.data.total > 0 ? (
                <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
              ) : null
            }
          />
        </Panel>
      </div>
    </>
  );
}

function LeaveDrawer({ leave, me, onClose }: { leave: Leave | null; me: Me; onClose: () => void }) {
  const decide = useDecideLeave();
  const [note, setNote] = useState("");
  const canDecide = can(me.role, "decideLeave") && leave?.status === "PENDING";
  const act = (status: "APPROVED" | "REJECTED") =>
    leave &&
    decide.mutate(
      { id: leave.id, status, note: note.trim() },
      {
        onSuccess: () => {
          toast.success(status === "APPROVED" ? "Leave approved" : "Leave rejected", `${leave.student_name ?? "The resident"} has been notified.`);
          setNote("");
          onClose();
        },
      },
    );
  return (
    <Drawer
      open={!!leave}
      onClose={onClose}
      busy={decide.isPending}
      title={leave?.student_name ?? "Leave request"}
      description={leave && <EnumPill domain="leaveStatus" value={leave.status} />}
      footer={
        canDecide ? (
          <>
            <Button variant="danger" icon={X} loading={decide.isPending && decide.variables?.status === "REJECTED"} disabled={decide.isPending} onClick={() => act("REJECTED")}>
              Reject
            </Button>
            <Button variant="primary" icon={Check} loading={decide.isPending && decide.variables?.status === "APPROVED"} disabled={decide.isPending} onClick={() => act("APPROVED")}>
              Approve
            </Button>
          </>
        ) : undefined
      }
    >
      {leave && (
        <div className="space-y-7">
          <Details
            items={[
              ["Resident", `${leave.student_name ?? "—"} (${leave.student_code ?? "—"})`],
              ["Leave", label(leave.leave_type)],
              ["Dates", `${formatRange(leave.from_date, leave.to_date)} (${nights(leave)})`],
              ["Destination", leave.destination ?? "Not given"],
              ["Guardian agrees", leave.guardian_consent ? "Yes" : "No"],
              ["Requested", formatDateTime(leave.created_at)],
              ...(leave.decided_at ? ([["Decided", formatDateTime(leave.decided_at)]] as [string, string][]) : []),
            ]}
          />
          <section>
            <h3 className="t-sub mb-2">Reason</h3>
            <p className="whitespace-pre-wrap text-body text-mist">{leave.reason}</p>
          </section>
          {leave.decision_note && (
            <section>
              <h3 className="t-sub mb-2">Decision note</h3>
              <p className="whitespace-pre-wrap text-body text-mist">{leave.decision_note}</p>
            </section>
          )}
          {canDecide ? (
            <div className="space-y-4">
              <Field label="Note to the resident" htmlFor="decision-note" help="Optional. Sent with the decision.">
                <Textarea
                  id="decision-note"
                  rows={3}
                  maxLength={1000}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </Field>
              <FormError error={decide.error} />
            </div>
          ) : (
            leave.status === "PENDING" && (
              <p className="rounded-control border border-hairline bg-lake-900/60 px-3 py-2.5 text-ui text-mist">
                Only the warden can approve or reject leave.
              </p>
            )
          )}
        </div>
      )}
    </Drawer>
  );
}

const FILTERS = [
  { value: "PENDING", label: "Waiting" },
  { value: "APPROVED", label: "Approved" },
  { value: "REJECTED", label: "Rejected" },
  { value: "COMPLETED", label: "Completed" },
  { value: "ALL", label: "All" },
] as const;

function OfficeLeave({ me }: { me: Me }) {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["value"]>("PENDING");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<Leave | null>(null);
  const list = useLeave({ status: filter === "ALL" ? undefined : filter, limit: PAGE, offset });
  const waiting = useLeave({ status: "PENDING", limit: 1 });

  const columns: Column<Leave>[] = [
    {
      key: "resident",
      header: "Resident",
      cell: (l) => (
        <span className="text-snow">
          {l.student_name ?? "—"}
          <span className="block text-small text-stone">{l.student_code}</span>
        </span>
      ),
    },
    { key: "type", header: "Leave", hideBelow: "sm", cell: (l) => label(l.leave_type) },
    {
      key: "dates",
      header: "Dates",
      cell: (l) => (
        <span className="whitespace-nowrap">
          {formatRange(l.from_date, l.to_date)}
          <span className="block text-small text-stone">{nights(l)}</span>
        </span>
      ),
    },
    { key: "destination", header: "Destination", hideBelow: "lg", cell: (l) => <span className="text-mist">{l.destination ?? "—"}</span> },
    { key: "requested", header: "Requested", hideBelow: "md", cell: (l) => <span className="whitespace-nowrap text-mist">{timeAgo(l.created_at)}</span> },
    { key: "status", header: "Status", cell: (l) => <EnumPill domain="leaveStatus" value={l.status} /> },
  ];

  return (
    <>
      <PageHeader
        title="Leave"
        description={
          can(me.role, "decideLeave")
            ? "Review requests and decide. Residents are notified of your decision straight away."
            : "Who is away and when. Only the warden can approve or reject requests."
        }
      />
      <div className="mb-4">
        <Segmented
          label="Filter leave by status"
          value={filter}
          onChange={(v) => {
            setFilter(v);
            setOffset(0);
          }}
          options={FILTERS.map((f) => ({
            value: f.value,
            label: f.label,
            count: f.value === "PENDING" ? waiting.data?.total : undefined,
          }))}
        />
      </div>
      <Panel flush>
        {list.isPending && !list.data ? (
          <div className="space-y-3 p-5">
            <Skeleton />
            <Skeleton className="w-2/3" />
          </div>
        ) : (
          <DataTable
            columns={columns}
            rows={list.data?.items}
            rowKey={(l) => l.id}
            loading={list.isFetching}
            error={list.error}
            onRetry={() => list.refetch()}
            onRowClick={setSelected}
            rowLabel={(l) => `Open leave request from ${l.student_name ?? "resident"}`}
            selectedKey={selected?.id}
            empty={{
              icon: Luggage,
              title: filter === "PENDING" ? "Nothing waiting for a decision" : "No leave in this view",
              description: filter === "PENDING" ? "New requests will appear here." : undefined,
            }}
            footer={
              list.data && list.data.total > 0 ? (
                <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
              ) : null
            }
          />
        )}
      </Panel>
      <LeaveDrawer leave={selected} me={me} onClose={() => setSelected(null)} />
    </>
  );
}

export function LeaveView() {
  const { data: me } = useMe();
  if (!me) return null;
  return isStaff(me.role) ? <OfficeLeave me={me} /> : <ResidentLeave />;
}
