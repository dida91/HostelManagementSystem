"use client";

import { MessageSquareWarning, Sparkles } from "lucide-react";
import { useState } from "react";

import { Guard } from "@/components/shell/guard";
import {
  Button,
  type Column,
  DataTable,
  Details,
  Drawer,
  EnumPill,
  ErrorState,
  Field,
  FieldRow,
  FormError,
  PageHeader,
  Pagination,
  Panel,
  Segmented,
  Select,
  SkeletonLines,
  Tag,
  Textarea,
} from "@/components/ui";
import type { Complaint, ComplaintDetail, ComplaintOverride } from "@/lib/api/types";
import { formatDateTime, timeAgo } from "@/lib/format";
import { label, OPEN_COMPLAINT_STATUSES, OPTIONS } from "@/lib/labels";
import { useComplaint, useComplaints, useOverrideComplaint } from "@/lib/queries";
import { toast } from "@/lib/store";

const PAGE = 15;
const FILTERS = {
  open: OPEN_COMPLAINT_STATUSES,
  resolved: ["RESOLVED", "CLOSED"],
  rejected: ["REJECTED"],
  all: undefined,
} as const;
type Filter = keyof typeof FILTERS;

const FIELDS: { key: "status" | "priority" | "category" | "department"; label: string; options: readonly string[] }[] = [
  { key: "status", label: "Status", options: OPTIONS.complaintStatus },
  { key: "priority", label: "Priority", options: OPTIONS.priority },
  { key: "category", label: "Category", options: OPTIONS.complaintCategory },
  { key: "department", label: "Send to", options: OPTIONS.department },
];

function OverrideForm({ complaint }: { complaint: ComplaintDetail }) {
  const save = useOverrideComplaint(complaint.id);
  const current = {
    status: complaint.status ?? "",
    priority: complaint.priority ?? "",
    category: complaint.category ?? "",
    department: complaint.department ?? "",
  };
  const [draft, setDraft] = useState(current);
  const [note, setNote] = useState("");
  const changes = Object.fromEntries(Object.entries(draft).filter(([k, v]) => v && v !== current[k as keyof typeof current]));
  // The API files a note with a status change and nowhere else; offering it
  // otherwise would drop it silently.
  const statusChanging = "status" in changes;
  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate({ ...(changes as ComplaintOverride), note: statusChanging ? note.trim() || null : null }, {
          onSuccess: () => {
            toast.success("Complaint updated", changes.status ? "The resident has been notified of the new status." : undefined);
            setNote("");
          },
        });
      }}
    >
      <FieldRow>
        {FIELDS.map((f) => (
          <Field key={f.key} label={f.label} htmlFor={`triage-${f.key}`}>
            <Select id={`triage-${f.key}`} value={draft[f.key]} onChange={(e) => setDraft({ ...draft, [f.key]: e.target.value })}>
              {!draft[f.key] && <option value="">Not set</option>}
              {f.options.map((o) => (
                <option key={o} value={o}>
                  {label(o)}
                </option>
              ))}
            </Select>
          </Field>
        ))}
      </FieldRow>
      <Field
        label="Staff note"
        htmlFor="triage-note"
        help={
          statusChanging
            ? "Internal. Saved with the status change; the resident doesn't see it."
            : "Change the status to add a note: notes are saved with status changes."
        }
      >
        <Textarea
          id="triage-note"
          rows={2}
          maxLength={1000}
          disabled={!statusChanging}
          aria-describedby="triage-note-help"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </Field>
      <FormError error={save.error} />
      <div className="flex items-center justify-between gap-3">
        <p className="text-small text-stone">
          {complaint.overridden_fields?.length
            ? `Set by staff: ${complaint.overridden_fields.map((f) => label(f).toLowerCase()).join(", ")}`
            : "Nothing changed by staff yet."}
        </p>
        <Button type="submit" variant="primary" loading={save.isPending} disabled={Object.keys(changes).length === 0}>
          Save changes
        </Button>
      </div>
    </form>
  );
}

function TriageDrawer({ id, onClose }: { id: string | null; onClose: () => void }) {
  const complaint = useComplaint(id);
  const c = complaint.data;
  const ai = c?.ai_analysis;
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      title="Complaint"
      description={
        c && (
          <span className="flex flex-wrap items-center gap-2">
            <EnumPill domain="complaintStatus" value={c.status} />
            {c.priority && <EnumPill domain="priority" value={c.priority} />}
            <span className="text-stone">Filed {timeAgo(c.created_at)}</span>
          </span>
        )
      }
    >
      {complaint.isError ? (
        <ErrorState error={complaint.error} onRetry={() => complaint.refetch()} />
      ) : !c ? (
        <SkeletonLines lines={8} />
      ) : (
        <div className="space-y-7">
          <blockquote className="whitespace-pre-wrap rounded-panel border border-hairline bg-lake-900/60 p-4 text-body text-snow">
            {c.raw_text}
          </blockquote>

          <section className="rounded-panel border border-hairline p-4">
            <h3 className="mb-3 flex items-center gap-2 text-ui font-medium text-mist">
              <Sparkles aria-hidden className="h-4 w-4 text-alpenglow" />
              AI suggestion
            </h3>
            {ai && ai.status === "SUCCESS" ? (
              <>
                <Details
                  items={[
                    ["Category", label(ai.category)],
                    ["Priority", label(ai.priority)],
                    ["Send to", label(ai.suggested_department)],
                    ["Tone", label(ai.sentiment)],
                    ["Location", ai.location ?? "Not stated"],
                    ["Confidence", ai.confidence != null ? `${Math.round(ai.confidence * 100)}%` : "—"],
                  ]}
                />
                {ai.summary && <p className="mt-3 text-ui italic text-mist">{ai.summary}</p>}
                <p className="mt-3 text-small text-stone">
                  {ai.model}, prompt {ai.prompt_version}. Advisory only.
                </p>
              </>
            ) : (
              <p className="text-ui text-stone">
                {ai ? "The AI couldn't analyse this one. Sort it by hand." : "Not analysed yet. Sort it by hand if it's urgent."}
              </p>
            )}
          </section>

          <section>
            <h3 className="t-sub mb-3">Triage</h3>
            <OverrideForm key={`${c.id}-${c.status}-${c.priority}`} complaint={c} />
          </section>
          <p className="text-small text-stone">Filed {formatDateTime(c.created_at)}{c.resolved_at ? `, resolved ${formatDateTime(c.resolved_at)}` : ""}.</p>
        </div>
      )}
    </Drawer>
  );
}

function Triage() {
  const [filter, setFilter] = useState<Filter>("open");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const status = FILTERS[filter] ? [...(FILTERS[filter] as readonly string[])] : undefined;
  const list = useComplaints({ status, limit: PAGE, offset });
  const openCount = useComplaints({ status: [...OPEN_COMPLAINT_STATUSES], limit: 1 });

  const columns: Column<Complaint>[] = [
    { key: "priority", header: "Priority", cell: (c) => (c.priority ? <EnumPill domain="priority" value={c.priority} /> : <Tag>Unsorted</Tag>) },
    { key: "report", header: "Report", cell: (c) => <span className="line-clamp-2 max-w-[52ch] text-snow">{c.summary ?? c.raw_text}</span> },
    { key: "category", header: "Category", hideBelow: "md", cell: (c) => <span className="text-mist">{label(c.category)}</span> },
    { key: "department", header: "Sent to", hideBelow: "lg", cell: (c) => <span className="text-mist">{label(c.department)}</span> },
    { key: "filed", header: "Filed", hideBelow: "sm", cell: (c) => <span className="whitespace-nowrap text-mist">{timeAgo(c.created_at)}</span> },
    { key: "status", header: "Status", cell: (c) => <EnumPill domain="complaintStatus" value={c.status} /> },
  ];

  return (
    <>
      <PageHeader
        title="Complaints"
        description="Sort, route and resolve what residents report. AI suggestions are advisory; every change is recorded, and residents hear about status changes."
      />
      <Segmented
        className="mb-4"
        label="Filter complaints"
        value={filter}
        onChange={(v) => {
          setFilter(v);
          setOffset(0);
        }}
        options={[
          { value: "open", label: "Open", count: openCount.data?.total },
          { value: "resolved", label: "Resolved" },
          { value: "rejected", label: "Rejected" },
          { value: "all", label: "All" },
        ]}
      />
      <Panel flush>
        <DataTable
          columns={columns}
          rows={list.data?.items}
          rowKey={(c) => c.id}
          loading={list.isFetching}
          error={list.error}
          onRetry={() => list.refetch()}
          onRowClick={(c) => setSelected(c.id)}
          rowLabel={(c) => `Open complaint: ${(c.summary ?? c.raw_text).slice(0, 60)}`}
          selectedKey={selected}
          empty={{
            icon: MessageSquareWarning,
            title: filter === "open" ? "No open complaints" : "Nothing in this view",
            description: filter === "open" ? "Everything reported has been dealt with." : undefined,
          }}
          footer={list.data && list.data.total > 0 ? <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} /> : null}
        />
      </Panel>
      <TriageDrawer id={selected} onClose={() => setSelected(null)} />
    </>
  );
}

export function TriageView() {
  return (
    <Guard capability="triage">
      <Triage />
    </Guard>
  );
}
