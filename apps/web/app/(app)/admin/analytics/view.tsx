"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { BarList, Meter, ORDINAL_SKY, StackedBar } from "@/components/charts";
import { Guard } from "@/components/shell/guard";
import { Button, ErrorState, Kpi, PageHeader, Panel, Segmented, SkeletonLines } from "@/components/ui";
import { ApiError } from "@/lib/api/client";
import { formatDateTime, formatHours, npr } from "@/lib/format";
import { label, OPTIONS } from "@/lib/labels";
import { useAnalytics, useInsights } from "@/lib/queries";

// Pipeline stages in order; the ramp runs light (just filed) to dark (finished).
const STAGES = [
  { key: "SUBMITTED", label: "Submitted" },
  { key: "TRIAGED", label: "Triaged" },
  { key: "IN_PROGRESS", label: "In progress" },
  { key: "RESOLVED", label: "Resolved" },
  { key: "CLOSED", label: "Closed or rejected" },
];

function Analytics() {
  const [days, setDays] = useState<"30" | "90" | "365">("30");
  const overview = useAnalytics(Number(days));
  const insight = useInsights();
  const a = overview.data;

  const categories = a
    ? Object.entries(a.complaints.by_category)
        .map(([key, value]) => ({ key, label: key === "uncategorised" ? "Not yet sorted" : label(key), value }))
        .sort((x, y) => y.value - x.value)
    : [];
  const stages = a
    ? STAGES.map((s, i) => ({
        key: s.key,
        label: s.label,
        color: ORDINAL_SKY[i],
        value: s.key === "CLOSED" ? (a.complaints.by_status.CLOSED ?? 0) + (a.complaints.by_status.REJECTED ?? 0) : (a.complaints.by_status[s.key] ?? 0),
      }))
    : [];
  const meals = a
    ? OPTIONS.mealType.filter((m) => a.mess.average_by_meal[m] !== undefined).map((m) => ({ key: m, label: label(m), value: a.mess.average_by_meal[m] }))
    : [];

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Every figure here is computed by the database. The AI briefing explains them; it never produces them."
        actions={
          <Segmented
            label="Time window"
            value={days}
            onChange={setDays}
            options={[
              { value: "30", label: "30 days" },
              { value: "90", label: "90 days" },
              { value: "365", label: "A year" },
            ]}
          />
        }
      />
      {overview.isError ? (
        <div className="panel">
          <ErrorState error={overview.error} onRetry={() => overview.refetch()} />
        </div>
      ) : (
        <div className={overview.isFetching && a ? "opacity-70 transition-opacity" : ""}>
          <section aria-label="Headline figures" className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
            <Kpi label="Beds occupied" loading={!a} value={a ? `${a.occupancy.occupancy_rate_percent}%` : "—"} context={a ? `${a.occupancy.occupied_beds} of ${a.occupancy.total_beds} beds` : undefined} />
            <Kpi
              label="Complaints filed"
              loading={!a}
              value={a?.complaints.total ?? "—"}
              context={
                a
                  ? a.complaints.change_percent === null
                    ? `${a.complaints.open} still open`
                    : `${a.complaints.change_percent > 0 ? "Up" : "Down"} ${Math.abs(a.complaints.change_percent)}% on the previous ${days} days`
                  : undefined
              }
            />
            <Kpi label="Median time to resolve" loading={!a} value={formatHours(a?.complaints.median_resolution_hours)} context="From filing to resolved" />
            <Kpi label="Mess rating" loading={!a} value={a?.mess.average_rating ? `${a.mess.average_rating} / 5` : "—"} context={a ? `${a.mess.responses} ratings` : undefined} />
          </section>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <Panel title="Complaints by category" description={`Filed in the last ${days} days`}>
              {!a ? <SkeletonLines lines={5} /> : categories.length === 0 ? <p className="text-ui text-stone">No complaints in this window.</p> : <BarList title="Complaints by category" data={categories} />}
            </Panel>
            <Panel title="Where complaints stand" description={`Status of those filed in the last ${days} days`}>
              {!a ? <SkeletonLines lines={3} /> : a.complaints.total === 0 ? <p className="text-ui text-stone">No complaints in this window.</p> : <StackedBar title="Complaints by status" segments={stages} />}
            </Panel>
            <Panel title="Beds and fees">
              {!a ? (
                <SkeletonLines lines={4} />
              ) : (
                <div className="space-y-6">
                  <Meter label="Beds occupied" value={a.occupancy.occupied_beds} max={Math.max(1, a.occupancy.total_beds)} display={`${a.occupancy.occupied_beds} of ${a.occupancy.total_beds}`} caption={`${a.occupancy.vacant_beds} beds free`} />
                  <Meter
                    label="Fees collected"
                    value={Number(a.fees.total_collected)}
                    max={Math.max(1, Number(a.fees.total_charged))}
                    display={`${a.fees.collection_rate_percent}%`}
                    caption={`${npr(a.fees.total_outstanding, true)} still owed across all residents`}
                  />
                </div>
              )}
            </Panel>
            <Panel title="Mess rating by meal" description={`Average out of 5, last ${days} days`}>
              {!a ? <SkeletonLines lines={4} /> : meals.length === 0 ? <p className="text-ui text-stone">No ratings in this window.</p> : <BarList title="Average rating by meal" data={meals} max={5} format={(v) => v.toFixed(1)} share={false} />}
            </Panel>
          </div>
        </div>
      )}

      <Panel
        className="mt-5"
        title="AI briefing"
        description="A short written summary of the figures above, for the warden."
        actions={
          <Button icon={Sparkles} loading={insight.isPending} onClick={() => insight.mutate(Number(days))}>
            {insight.data ? "Write it again" : "Write a briefing"}
          </Button>
        }
      >
        {insight.isError ? (
          <p className="text-ui text-laligurans-300">
            {insight.error instanceof ApiError && insight.error.status === 503
              ? "AI commentary is unavailable right now. The figures above are unaffected."
              : insight.error instanceof ApiError
                ? insight.error.message
                : "The briefing couldn't be written."}
          </p>
        ) : insight.data ? (
          <>
            <p className="max-w-[70ch] whitespace-pre-wrap text-body text-snow">{insight.data.narrative}</p>
            <p className="mt-4 text-small text-stone">
              {insight.data.disclaimer} Figures as of {formatDateTime(insight.data.metrics.generated_at)}.
            </p>
          </>
        ) : (
          <p className="text-ui text-stone">Nothing written yet. The briefing uses the same {days}-day window as the figures.</p>
        )}
      </Panel>
    </>
  );
}

export function AnalyticsView() {
  return (
    <Guard capability="viewAnalytics">
      <Analytics />
    </Guard>
  );
}
