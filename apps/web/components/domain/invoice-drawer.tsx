"use client";

import { Banknote } from "lucide-react";

import { Button, Details, Drawer, EnumPill, ErrorState, SkeletonLines } from "@/components/ui";
import { formatDate, npr, periodLabel } from "@/lib/format";
import { useInvoice } from "@/lib/queries";

/** One invoice: its lines and what remains to pay. Figures come from the API. */
export function InvoiceDrawer({
  id,
  onClose,
  onRecordPayment,
  showResident,
}: {
  id: string | null;
  onClose: () => void;
  onRecordPayment?: (invoice: { id: string; student_id: string; outstanding: string }) => void;
  showResident?: boolean;
}) {
  const invoice = useInvoice(id);
  const data = invoice.data;
  const payable = data && Number(data.outstanding_npr) > 0 && data.status !== "VOID";
  return (
    <Drawer
      open={!!id}
      onClose={onClose}
      title={data ? `Invoice ${data.invoice_number}` : "Invoice"}
      description={data && <EnumPill domain="invoiceStatus" value={data.status} />}
      footer={
        onRecordPayment && payable ? (
          <Button
            variant="primary"
            icon={Banknote}
            onClick={() =>
              onRecordPayment({ id: data.id, student_id: data.student_id, outstanding: data.outstanding_npr })
            }
          >
            Record payment
          </Button>
        ) : undefined
      }
    >
      {invoice.isError ? (
        <ErrorState error={invoice.error} onRetry={() => invoice.refetch()} />
      ) : !data ? (
        <SkeletonLines lines={6} />
      ) : (
        <div className="space-y-7">
          <Details
            items={[
              ...(showResident
                ? ([["Resident", `${data.student_name ?? "—"} (${data.student_code ?? "—"})`]] as [string, string][])
                : []),
              ["Period", `${formatDate(data.period_start)} to ${formatDate(data.period_end)}`],
              ["Due", formatDate(data.due_date)],
              ["Billing", data.billing_period ? `Monthly bill, ${periodLabel(data.billing_period)}` : "Issued by the office"],
            ]}
          />

          <section>
            <h3 className="t-sub mb-3">Charges</h3>
            <ul className="rows rounded-panel border border-hairline">
              {data.line_items.map((li, i) => (
                <li key={i} className="flex items-start justify-between gap-4 px-4 py-3 text-ui">
                  <span className="text-snow">
                    {li.description}
                    {Number(li.quantity) !== 1 && (
                      <span className="block text-small text-stone">
                        {Number(li.quantity)} × {npr(li.unit_amount_npr)}
                      </span>
                    )}
                  </span>
                  <span className="shrink-0 text-snow tabular">
                    {npr(Number(li.quantity) * Number(li.unit_amount_npr))}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <dl className="space-y-2 text-ui">
            <div className="flex justify-between">
              <dt className="text-mist">Total</dt>
              <dd className="text-snow tabular">{npr(data.total_npr)}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-mist">Paid</dt>
              <dd className="text-snow tabular">{npr(data.paid_npr)}</dd>
            </div>
            <div className="flex justify-between border-t border-hairline pt-2">
              <dt className="font-medium text-snow">Still to pay</dt>
              <dd className="t-sub text-snow tabular">{npr(data.outstanding_npr)}</dd>
            </div>
          </dl>

          {data.note && (
            <section>
              <h3 className="t-sub mb-1">Note</h3>
              <p className="whitespace-pre-wrap text-ui text-mist">{data.note}</p>
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}
