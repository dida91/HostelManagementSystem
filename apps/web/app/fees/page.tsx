"use client";

import { useQuery } from "@tanstack/react-query";

import { Badge, Card } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api } from "@/lib/api";

const npr = (v: string | number) =>
  `NPR ${Number(v).toLocaleString("en-NP", { minimumFractionDigits: 2 })}`;

export default function FeesPage() {
  const { data: balance } = useQuery({ queryKey: ["balance"], queryFn: () => api.balance() });
  const { data: ledger } = useQuery({ queryKey: ["ledger"], queryFn: () => api.ledger() });

  return (
    <Shell>
      <h1 className="mb-2 text-xl font-semibold text-slate-800">Fees</h1>
      <p className="mb-6 text-sm text-slate-500">
        Every figure is calculated from your ledger by the system, not estimated.
      </p>

      <div className="mb-6 grid gap-5 sm:grid-cols-3">
        <Card title="Outstanding">
          <p className="text-2xl font-semibold text-brand-700">
            {balance ? npr(balance.outstanding) : "—"}
          </p>
        </Card>
        <Card title="Total charged">
          <p className="text-2xl font-semibold text-slate-700">
            {balance ? npr(balance.total_charged) : "—"}
          </p>
        </Card>
        <Card title="Total paid">
          <p className="text-2xl font-semibold text-slate-700">
            {balance ? npr(balance.total_paid) : "—"}
          </p>
        </Card>
      </div>

      <Card title="Ledger">
        {ledger?.length ? (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-left text-xs uppercase text-slate-500">
                <th className="pb-2">Date</th>
                <th className="pb-2">Description</th>
                <th className="pb-2">Type</th>
                <th className="pb-2 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {ledger.map((e) => (
                <tr key={e.id} className="border-b border-slate-50">
                  <td className="py-2 text-slate-500">
                    {new Date(e.occurred_at).toLocaleDateString()}
                  </td>
                  <td className="py-2 text-slate-700">{e.description}</td>
                  <td className="py-2">
                    <Badge value={e.entry_type === "DEBIT" ? "MEDIUM" : "POSITIVE"} />
                  </td>
                  <td
                    className={`py-2 text-right font-medium ${
                      e.entry_type === "DEBIT" ? "text-slate-800" : "text-emerald-700"
                    }`}
                  >
                    {e.entry_type === "DEBIT" ? "+" : "−"}
                    {npr(e.amount_npr)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-slate-500">No ledger entries.</p>
        )}
      </Card>
    </Shell>
  );
}
