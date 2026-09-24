"use client";

import { Banknote, CalendarPlus, Ellipsis, FilePlus2, Pencil, Plus, ReceiptText, Trash2 } from "lucide-react";
import { useState } from "react";

import { Meter } from "@/components/charts";
import { InvoiceDrawer } from "@/components/domain/invoice-drawer";
import { Guard } from "@/components/shell/guard";
import {
  Button,
  type Column,
  ConfirmDialog,
  DataTable,
  EnumPill,
  IconButton,
  Kpi,
  Menu,
  Money,
  PageHeader,
  Pagination,
  Panel,
  Segmented,
  Select,
  StatusPill,
} from "@/components/ui";
import type { FeeStructure, Invoice } from "@/lib/api/types";
import { formatDate, npr, periodLabel, recentPeriods, todayISO } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useAnalytics, useDeleteStructure, useFeeStructures, useInvoices, useMe } from "@/lib/queries";
import { toast } from "@/lib/store";

import { GenerateModal, InvoiceModal, PaymentModal, StructureModal } from "./modals";

const PAGE = 15;

function structureState(s: FeeStructure): { label: string; tone: "success" | "info" | "neutral" } {
  const today = todayISO();
  if (s.effective_from > today) return { label: "Upcoming", tone: "info" };
  if (s.effective_to && s.effective_to < today) return { label: "Ended", tone: "neutral" };
  return { label: "In effect", tone: "success" };
}

function Invoices({ onOpen, selected }: { onOpen: (id: string) => void; selected: string | null }) {
  const [status, setStatus] = useState("");
  const [period, setPeriod] = useState("");
  const [offset, setOffset] = useState(0);
  const list = useInvoices({ status: status || undefined, billing_period: period || undefined, limit: PAGE, offset });
  const columns: Column<Invoice>[] = [
    { key: "number", header: "Invoice", hideBelow: "sm", cell: (i) => <span className="whitespace-nowrap text-snow">{i.invoice_number}</span> },
    {
      key: "resident",
      header: "Resident",
      cell: (i) => (
        <span className="text-snow">
          {i.student_name ?? "—"}
          <span className="block text-small text-stone">{i.student_code}</span>
        </span>
      ),
    },
    {
      key: "period",
      header: "For",
      hideBelow: "md",
      cell: (i) => <span className="text-mist">{i.billing_period ? periodLabel(i.billing_period) : `${formatDate(i.period_start)} to ${formatDate(i.period_end)}`}</span>,
    },
    { key: "due", header: "Due", hideBelow: "sm", cell: (i) => <span className="whitespace-nowrap">{formatDate(i.due_date)}</span> },
    { key: "status", header: "Status", cell: (i) => <EnumPill domain="invoiceStatus" value={i.status} /> },
    { key: "total", header: "Total", align: "right", cell: (i) => <span className="text-snow">{npr(i.total_npr)}</span> },
  ];
  return (
    <Panel
      title="Invoices"
      flush
      actions={
        <div className="flex flex-wrap gap-2">
          <Select aria-label="Filter by status" className="min-h-9 w-[9.5rem] sm:w-40" value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }}>
            <option value="">All statuses</option>
            {OPTIONS.invoiceStatus.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </Select>
          <Select aria-label="Filter by billing month" className="min-h-9 w-[9.5rem] sm:w-44" value={period} onChange={(e) => { setPeriod(e.target.value); setOffset(0); }}>
            <option value="">All months</option>
            {recentPeriods().map((p) => (
              <option key={p} value={p}>
                {periodLabel(p)}
              </option>
            ))}
          </Select>
        </div>
      }
    >
      <DataTable
        columns={columns}
        rows={list.data?.items}
        rowKey={(i) => i.id}
        loading={list.isFetching}
        error={list.error}
        onRetry={() => list.refetch()}
        onRowClick={(i) => onOpen(i.id)}
        rowLabel={(i) => `Open invoice ${i.invoice_number}`}
        selectedKey={selected}
        empty={{ icon: ReceiptText, title: status || period ? "No invoices match" : "No invoices yet", description: status || period ? "Clear a filter to see more." : "Bill a month, or issue a one-off invoice." }}
        footer={list.data && list.data.total > 0 ? <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} /> : null}
      />
    </Panel>
  );
}

function Schedule({ manage }: { manage: boolean }) {
  const structures = useFeeStructures();
  const remove = useDeleteStructure();
  const [editing, setEditing] = useState<FeeStructure | "new" | null>(null);
  const [deleting, setDeleting] = useState<FeeStructure | null>(null);
  const columns: Column<FeeStructure>[] = [
    {
      key: "name",
      header: "Fee",
      cell: (s) => (
        <span className="text-snow">
          {s.name}
          {s.description && <span className="block text-small text-stone">{s.description}</span>}
        </span>
      ),
    },
    { key: "cadence", header: "Billed", hideBelow: "sm", cell: (s) => (s.cadence === "MONTHLY" ? "Every month" : "One-time") },
    { key: "window", header: "In effect", hideBelow: "md", cell: (s) => <span className="whitespace-nowrap text-mist">{formatDate(s.effective_from)} to {s.effective_to ? formatDate(s.effective_to) : "ongoing"}</span> },
    { key: "state", header: "State", cell: (s) => { const st = structureState(s); return <StatusPill tone={st.tone}>{st.label}</StatusPill>; } },
    { key: "amount", header: "Amount", align: "right", cell: (s) => <span className="text-snow">{npr(s.amount_npr)}</span> },
    ...(manage
      ? ([
          {
            key: "actions",
            header: <span className="sr-only">Actions</span>,
            align: "right",
            cell: (s: FeeStructure) => (
              <Menu
                label={`${s.name} actions`}
                items={[
                  { label: "Edit fee", icon: Pencil, onSelect: () => setEditing(s) },
                  { label: "Delete fee", icon: Trash2, tone: "danger", onSelect: () => setDeleting(s) },
                ]}
                trigger={(props) => <IconButton {...props} icon={Ellipsis} label={`${s.name} actions`} size="sm" />}
              />
            ),
          },
        ] as Column<FeeStructure>[])
      : []),
  ];
  return (
    <Panel
      title="Fee schedule"
      description="Room rent comes from each room. These are charged on top."
      flush
      actions={manage && <Button size="sm" icon={Plus} onClick={() => setEditing("new")}>Add fee</Button>}
    >
      <DataTable
        columns={columns}
        rows={structures.data}
        rowKey={(s) => s.id}
        loading={structures.isFetching}
        error={structures.error}
        onRetry={() => structures.refetch()}
        empty={{ icon: ReceiptText, title: "No fees besides room rent", description: manage ? "Add a monthly mess or utilities fee, for example." : undefined }}
      />
      {editing && <StructureModal key={editing === "new" ? "new" : editing.id} structure={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      <ConfirmDialog
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title={`Delete ${deleting?.name ?? "fee"}?`}
        confirmLabel="Delete fee"
        tone="danger"
        loading={remove.isPending}
        onConfirm={() =>
          deleting &&
          remove.mutate(deleting.id, {
            onSuccess: () => {
              toast.success("Fee deleted");
              setDeleting(null);
            },
          })
        }
      >
        <p>Future monthly bills won’t include it. Invoices already issued keep their charges. To stop a fee from a date instead, edit its end date.</p>
      </ConfirmDialog>
    </Panel>
  );
}

function OfficeFees() {
  const { data: me } = useMe();
  const analytics = useAnalytics(30);
  const [tab, setTab] = useState<"invoices" | "schedule">("invoices");
  const [openInvoice, setOpenInvoice] = useState<string | null>(null);
  const [modal, setModal] = useState<"payment" | "invoice" | "generate" | null>(null);
  const [paymentPreset, setPaymentPreset] = useState<{ studentId: string; invoiceId: string; amount: string } | undefined>();
  if (!me) return null;
  const f = analytics.data?.fees;

  return (
    <>
      <PageHeader
        title="Fees"
        description="Invoices, payments and the fee schedule. Balances are always calculated from each resident's ledger."
        actions={
          <>
            {can(me.role, "generateInvoices") && (
              <Button icon={CalendarPlus} onClick={() => setModal("generate")}>
                Bill a month
              </Button>
            )}
            {can(me.role, "issueInvoices") && (
              <Button icon={FilePlus2} onClick={() => setModal("invoice")}>
                New invoice
              </Button>
            )}
            {can(me.role, "recordPayments") && (
              <Button variant="primary" icon={Banknote} onClick={() => { setPaymentPreset(undefined); setModal("payment"); }}>
                Record payment
              </Button>
            )}
          </>
        }
      />
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1.3fr)]">
        <Kpi label="Outstanding" loading={analytics.isPending} value={f ? <Money value={f.total_outstanding} whole /> : "—"} emphasis={f && Number(f.total_outstanding) > 0 ? "warm" : undefined} context="Owed by residents right now" />
        <Kpi label="Collected" loading={analytics.isPending} value={f ? <Money value={f.total_collected} whole /> : "—"} context={f ? `of ${npr(f.total_charged, true)} charged` : undefined} />
        <Panel>
          {f ? (
            <Meter
              label="Collection rate"
              value={Number(f.total_collected)}
              max={Math.max(1, Number(f.total_charged))}
              display={`${f.collection_rate_percent}%`}
              caption="Share of everything charged that has been paid."
            />
          ) : (
            <p className="text-ui text-stone">{analytics.isError ? "Collection figures didn't load." : "Loading…"}</p>
          )}
        </Panel>
      </div>

      <Segmented
        className="mb-4 mt-8"
        label="Fees views"
        value={tab}
        onChange={setTab}
        options={[
          { value: "invoices", label: "Invoices" },
          { value: "schedule", label: "Fee schedule" },
        ]}
      />
      {tab === "invoices" ? <Invoices onOpen={setOpenInvoice} selected={openInvoice} /> : <Schedule manage={can(me.role, "manageFeeStructures")} />}

      <InvoiceDrawer
        id={openInvoice}
        showResident
        onClose={() => setOpenInvoice(null)}
        onRecordPayment={
          can(me.role, "recordPayments")
            ? (inv) => {
                setPaymentPreset({ studentId: inv.student_id, invoiceId: inv.id, amount: inv.outstanding });
                setOpenInvoice(null);
                setModal("payment");
              }
            : undefined
        }
      />
      {modal === "payment" && <PaymentModal preset={paymentPreset} onClose={() => setModal(null)} />}
      {modal === "invoice" && <InvoiceModal onClose={() => setModal(null)} />}
      {modal === "generate" && <GenerateModal onClose={() => setModal(null)} />}
    </>
  );
}

export function OfficeFeesView() {
  return (
    <Guard capability="viewFees">
      <OfficeFees />
    </Guard>
  );
}
