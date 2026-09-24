"use client";

import { ReceiptText, ScrollText } from "lucide-react";
import { useState } from "react";

import { InvoiceDrawer } from "@/components/domain/invoice-drawer";
import { ResidentOnly } from "@/components/shell/guard";
import { type Column, DataTable, EnumPill, Kpi, Money, PageHeader, Pagination, Panel } from "@/components/ui";
import type { Invoice, LedgerEntry } from "@/lib/api/types";
import { formatDate, formatDayMonth, npr, periodLabel } from "@/lib/format";
import { ledgerDescription } from "@/lib/labels";
import { useBalance, useInvoices, useLedger } from "@/lib/queries";

const PAGE = 10;

function Resident() {
  const balance = useBalance();
  const [offset, setOffset] = useState(0);
  const invoices = useInvoices({ limit: PAGE, offset });
  const ledger = useLedger();
  const [openId, setOpenId] = useState<string | null>(null);
  const outstanding = Number(balance.data?.outstanding ?? 0);
  const overdue = invoices.data?.items.some((i) => i.status === "OVERDUE");

  const invoiceColumns: Column<Invoice>[] = [
    { key: "number", header: "Invoice", hideBelow: "sm", cell: (i) => <span className="text-snow">{i.invoice_number}</span> },
    {
      key: "period",
      header: "For",
      cell: (i) => (i.billing_period ? periodLabel(i.billing_period) : `${formatDayMonth(i.period_start)} – ${formatDate(i.period_end)}`),
    },
    { key: "due", header: "Due", hideBelow: "sm", cell: (i) => <span className="whitespace-nowrap">{formatDate(i.due_date)}</span> },
    { key: "status", header: "Status", cell: (i) => <EnumPill domain="invoiceStatus" value={i.status} /> },
    { key: "total", header: "Total", align: "right", cell: (i) => <span className="text-snow">{npr(i.total_npr)}</span> },
  ];
  const ledgerColumns: Column<LedgerEntry>[] = [
    { key: "date", header: "Date", hideBelow: "sm", cell: (e) => <span className="whitespace-nowrap text-mist">{formatDate(e.occurred_at)}</span> },
    {
      key: "description",
      header: "Description",
      cell: (e) => (
        <span className="text-snow">
          {ledgerDescription(e.description)}
          <span className="block text-small text-stone sm:hidden">{formatDate(e.occurred_at)}</span>
        </span>
      ),
    },
    { key: "charge", header: "Charged", align: "right", cell: (e) => (e.entry_type === "DEBIT" ? npr(e.amount_npr) : "") },
    {
      key: "paid",
      header: "Paid",
      align: "right",
      cell: (e) => (e.entry_type === "CREDIT" ? <span className="text-terrace-300">{npr(e.amount_npr)}</span> : ""),
    },
  ];

  return (
    <>
      <PageHeader
        title="Fees"
        description="Your bills and payments. Every figure is calculated from your account by the office system."
      />
      <div className="grid gap-5 sm:grid-cols-3">
        <Kpi
          label="Outstanding"
          loading={balance.isPending}
          value={balance.data ? <Money value={balance.data.outstanding} /> : "—"}
          emphasis={overdue ? "alert" : outstanding > 0 ? "warm" : undefined}
          context={overdue ? "An invoice is overdue. Pay at the hostel office." : outstanding > 0 ? "Pay at the hostel office." : "Nothing to pay."}
        />
        <Kpi label="Charged to date" loading={balance.isPending} value={balance.data ? <Money value={balance.data.total_charged} /> : "—"} />
        <Kpi label="Paid to date" loading={balance.isPending} value={balance.data ? <Money value={balance.data.total_paid} /> : "—"} />
      </div>

      <Panel title="Invoices" className="mt-5" flush>
        <DataTable
          columns={invoiceColumns}
          rows={invoices.data?.items}
          rowKey={(i) => i.id}
          loading={invoices.isFetching}
          error={invoices.error}
          onRetry={() => invoices.refetch()}
          onRowClick={(i) => setOpenId(i.id)}
          rowLabel={(i) => `Open invoice ${i.invoice_number}`}
          selectedKey={openId}
          empty={{ icon: ReceiptText, title: "No invoices yet", description: "Monthly bills appear here on the 1st." }}
          footer={
            invoices.data && invoices.data.total > 0 ? (
              <Pagination total={invoices.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
            ) : null
          }
        />
      </Panel>

      <Panel title="Account history" description="Every charge and payment, newest first." className="mt-5" flush>
        <DataTable
          columns={ledgerColumns}
          rows={ledger.data}
          rowKey={(e) => e.id}
          loading={ledger.isFetching}
          error={ledger.error}
          onRetry={() => ledger.refetch()}
          empty={{ icon: ScrollText, title: "No charges or payments yet" }}
        />
      </Panel>
      <InvoiceDrawer id={openId} onClose={() => setOpenId(null)} />
    </>
  );
}

export function FeesView() {
  return (
    <ResidentOnly officeHref="/admin/fees" officeLabel="Open office fees">
      <Resident />
    </ResidentOnly>
  );
}
