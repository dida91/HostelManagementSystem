"use client";

import { Luggage, Megaphone, MessageSquareWarning } from "lucide-react";
import { useMemo } from "react";

import { Meter } from "@/components/charts";
import { Button, EmptyState, EnumPill, ErrorState, Kpi, Money, Panel, SkeletonLines, Tag, TextLink } from "@/components/ui";
import type { Me } from "@/lib/api/types";
import { formatRange, timeAgo } from "@/lib/format";
import { label, OPEN_COMPLAINT_STATUSES } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useAnalytics, useBlocks, useComplaints, useLeave, useNotices, useRooms } from "@/lib/queries";

import { Hero } from "./hero";

const PRIORITY_RANK: Record<string, number> = { URGENT: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

export function OfficeHome({ me }: { me: Me }) {
  const analytics = useAnalytics(30);
  const open = useComplaints({ status: OPEN_COMPLAINT_STATUSES, limit: 50 });
  const pending = useLeave({ status: "PENDING", limit: 5 });
  const rooms = useRooms();
  const blocks = useBlocks();
  const notices = useNotices();

  const attention = useMemo(
    () =>
      [...(open.data?.items ?? [])]
        .sort(
          (a, b) =>
            (PRIORITY_RANK[a.priority ?? ""] ?? 4) - (PRIORITY_RANK[b.priority ?? ""] ?? 4) ||
            b.created_at.localeCompare(a.created_at),
        )
        .slice(0, 5),
    [open.data],
  );

  const byBlock = useMemo(() => {
    const totals = new Map<string, { beds: number; occupied: number }>();
    for (const r of rooms.data ?? []) {
      const t = totals.get(r.block_id) ?? { beds: 0, occupied: 0 };
      t.beds += r.bed_count;
      t.occupied += r.occupied;
      totals.set(r.block_id, t);
    }
    return (blocks.data ?? [])
      .map((b) => ({ ...b, ...(totals.get(b.id) ?? { beds: 0, occupied: 0 }) }))
      .filter((b) => b.beds > 0);
  }, [rooms.data, blocks.data]);

  const a = analytics.data;
  const openCount = open.data?.total ?? 0;
  const pendingCount = pending.data?.total ?? 0;

  return (
    <>
      <Hero name={me.full_name}>
        <div className="flex flex-wrap items-center gap-3">
          <Button variant={openCount > 0 ? "primary" : "secondary"} icon={MessageSquareWarning} href="/admin/complaints">
            {open.isPending
              ? "Complaints"
              : openCount === 0
                ? "No open complaints"
                : `${openCount} open ${openCount === 1 ? "complaint" : "complaints"}`}
          </Button>
          <Button variant={pendingCount > 0 && openCount === 0 ? "primary" : "secondary"} icon={Luggage} href="/leave">
            {pending.isPending
              ? "Leave"
              : pendingCount === 0
                ? "No leave waiting"
                : `${pendingCount} leave ${pendingCount === 1 ? "request" : "requests"} waiting`}
          </Button>
        </div>
      </Hero>

      <section aria-label="Last 30 days" className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label="Beds occupied"
          loading={analytics.isPending}
          value={a ? `${a.occupancy.occupancy_rate_percent}%` : "—"}
          context={a ? `${a.occupancy.occupied_beds} of ${a.occupancy.total_beds} beds` : undefined}
        />
        <Kpi
          label="Open complaints"
          loading={analytics.isPending}
          value={a ? a.complaints.open : "—"}
          emphasis={a && a.complaints.open > 0 ? "warm" : undefined}
          context={
            a
              ? a.complaints.change_percent === null
                ? `${a.complaints.total} filed in 30 days`
                : `${a.complaints.total} filed, ${a.complaints.change_percent > 0 ? "up" : "down"} ${Math.abs(a.complaints.change_percent)}% on the month before`
              : undefined
          }
        />
        <Kpi
          label="Fees outstanding"
          loading={analytics.isPending}
          value={a ? <Money value={a.fees.total_outstanding} whole /> : "—"}
          context={a ? `${a.fees.collection_rate_percent}% of charges collected` : undefined}
        />
        <Kpi
          label="Mess rating"
          loading={analytics.isPending}
          value={a?.mess.average_rating ? `${a.mess.average_rating} / 5` : "—"}
          context={a ? `${a.mess.responses} ratings in 30 days` : undefined}
        />
      </section>
      {analytics.isError && (
        <div className="panel mt-5">
          <ErrorState error={analytics.error} onRetry={() => analytics.refetch()} />
        </div>
      )}

      <div className="mt-5 grid gap-5 xl:grid-cols-3">
        <Panel
          className="xl:col-span-2"
          title="Needs attention"
          description="Open complaints, most urgent first"
          actions={<TextLink href="/admin/complaints">Triage</TextLink>}
          flush
        >
          {open.isPending ? (
            <SkeletonLines lines={5} className="p-5" />
          ) : open.isError ? (
            <ErrorState error={open.error} onRetry={() => open.refetch()} />
          ) : attention.length === 0 ? (
            <EmptyState compact icon={MessageSquareWarning} title="No open complaints" description="Everything reported has been resolved." />
          ) : (
            <ul className="rows px-5 pb-2">
              {attention.map((c) => (
                <li key={c.id} className="flex items-start gap-4 py-3.5">
                  <div className="w-20 shrink-0 pt-0.5">
                    {c.priority ? <EnumPill domain="priority" value={c.priority} /> : <Tag>Unsorted</Tag>}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-ui text-snow">{c.summary ?? c.raw_text}</p>
                    <p className="mt-1 flex flex-wrap gap-x-3 text-small text-stone">
                      <span>{c.category ? label(c.category) : "Not yet categorised"}</span>
                      <span>{timeAgo(c.created_at)}</span>
                    </p>
                  </div>
                  <EnumPill domain="complaintStatus" value={c.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Leave waiting" actions={<TextLink href="/leave">Review</TextLink>} flush>
          {pending.isPending ? (
            <SkeletonLines lines={4} className="p-5" />
          ) : pending.isError ? (
            <ErrorState error={pending.error} onRetry={() => pending.refetch()} />
          ) : pending.data.items.length === 0 ? (
            <EmptyState compact icon={Luggage} title="Nothing to decide" description="New leave requests will appear here." />
          ) : (
            <ul className="rows px-5 pb-2">
              {pending.data.items.map((l) => (
                <li key={l.id} className="py-3.5">
                  <p className="text-ui text-snow">{l.student_name ?? "Resident"}</p>
                  <p className="mt-0.5 text-small text-stone">
                    {label(l.leave_type)}, {formatRange(l.from_date, l.to_date)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Panel title="Beds by block" actions={<TextLink href="/admin/rooms">Rooms</TextLink>}>
          {rooms.isPending || blocks.isPending ? (
            <SkeletonLines lines={3} />
          ) : rooms.isError || blocks.isError ? (
            <p className="text-ui text-laligurans-300">Room occupancy didn’t load.</p>
          ) : byBlock.length === 0 ? (
            <p className="text-ui text-stone">No rooms have been set up yet.</p>
          ) : (
            <div className="space-y-5">
              {byBlock.map((b) => (
                <Meter
                  key={b.id}
                  label={b.name}
                  value={b.occupied}
                  max={b.beds}
                  display={`${b.occupied} of ${b.beds} beds`}
                />
              ))}
            </div>
          )}
        </Panel>

        <Panel
          title="Notices"
          actions={
            can(me.role, "manageNotices") ? (
              <Button size="sm" icon={Megaphone} href="/notices">
                Post a notice
              </Button>
            ) : (
              <TextLink href="/notices">All notices</TextLink>
            )
          }
        >
          {notices.isPending ? (
            <SkeletonLines lines={3} />
          ) : notices.isError ? (
            <p className="text-ui text-laligurans-300">Notices didn’t load.</p>
          ) : notices.data.length === 0 ? (
            <p className="text-ui text-stone">No notices are live.</p>
          ) : (
            <ul className="space-y-4">
              {notices.data.slice(0, 3).map((n) => (
                <li key={n.id}>
                  <p className="text-ui font-medium text-snow">{n.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-ui text-mist">{n.body}</p>
                  <p className="mt-1 text-small text-stone">{timeAgo(n.publish_at)}</p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}
