"use client";

import { useMutation, useQuery } from "@tanstack/react-query";

import { Button, Card, ErrorNote } from "@/components/ui";
import { Shell } from "@/components/shell";
import { api, ApiError } from "@/lib/api";

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-800">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-400">{hint}</p>}
    </div>
  );
}

export default function AnalyticsPage() {
  const { data } = useQuery({ queryKey: ["analytics"], queryFn: api.analyticsOverview });
  const insight = useMutation({ mutationFn: () => api.insights(30) });

  const o = data?.occupancy;
  const c = data?.complaints;
  const f = data?.fees;
  const m = data?.mess;

  return (
    <Shell>
      <h1 className="mb-2 text-xl font-semibold text-slate-800">Analytics</h1>
      <p className="mb-6 text-sm text-slate-500">
        All figures are computed from the database. AI commentary explains them; it never
        produces them.
      </p>

      <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Occupancy"
          value={o ? `${o.occupancy_rate_percent}%` : "—"}
          hint={o ? `${o.occupied_beds} of ${o.total_beds} beds` : undefined}
        />
        <Stat
          label="Open complaints"
          value={c ? String(c.open) : "—"}
          hint={
            c?.change_percent != null
              ? `${c.change_percent > 0 ? "+" : ""}${c.change_percent}% vs previous 30 days`
              : "no prior period"
          }
        />
        <Stat
          label="Fees outstanding"
          value={f ? `NPR ${Number(f.total_outstanding).toLocaleString()}` : "—"}
          hint={f ? `${f.collection_rate_percent}% collected` : undefined}
        />
        <Stat
          label="Mess rating"
          value={m?.average_rating ? `${m.average_rating}/5` : "—"}
          hint={m ? `${m.responses} responses` : undefined}
        />
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <Card title="Complaints by category">
          {c && Object.keys(c.by_category).length ? (
            <ul className="space-y-2">
              {Object.entries(c.by_category)
                .sort((a, b) => b[1] - a[1])
                .map(([cat, n]) => {
                  const max = Math.max(...Object.values(c.by_category));
                  return (
                    <li key={cat} className="flex items-center gap-3 text-sm">
                      <span className="w-32 shrink-0 text-slate-600">
                        {cat.replaceAll("_", " ").toLowerCase()}
                      </span>
                      <span
                        className="h-2 rounded-full bg-brand-500"
                        style={{ width: `${Math.max(6, (n / max) * 100)}%` }}
                        aria-hidden
                      />
                      <span className="text-slate-500">{n}</span>
                    </li>
                  );
                })}
            </ul>
          ) : (
            <p className="text-sm text-slate-500">No complaints in this window.</p>
          )}
          {c?.median_resolution_hours != null && (
            <p className="mt-4 text-xs text-slate-500">
              Median resolution time: {c.median_resolution_hours} hours
            </p>
          )}
        </Card>

        <Card
          title="AI briefing"
          actions={
            <Button variant="ghost" onClick={() => insight.mutate()} disabled={insight.isPending}>
              {insight.isPending ? "Generating…" : "Generate"}
            </Button>
          }
        >
          {insight.isError && (
            <ErrorNote
              message={
                insight.error instanceof ApiError && insight.error.status === 503
                  ? "AI commentary is unavailable. The figures above are unaffected."
                  : "Could not generate the briefing."
              }
            />
          )}
          {insight.data ? (
            <>
              <p className="whitespace-pre-wrap text-sm text-slate-800">
                {insight.data.narrative}
              </p>
              <p className="mt-3 text-xs text-slate-400">{insight.data.disclaimer}</p>
            </>
          ) : (
            !insight.isError && (
              <p className="text-sm text-slate-500">
                Generate a short written summary of the figures above.
              </p>
            )
          )}
        </Card>
      </div>
    </Shell>
  );
}
