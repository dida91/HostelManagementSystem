"use client";

import { BedDouble, Luggage, MessageSquareWarning, MessagesSquare } from "lucide-react";
import Link from "next/link";

import { Button, EmptyState, EnumPill, ErrorState, Kpi, Money, Panel, SkeletonLines, TextLink } from "@/components/ui";
import type { Me } from "@/lib/api/types";
import { formatDate, formatRange, timeAgo, WEEKDAYS } from "@/lib/format";
import { label } from "@/lib/labels";
import { useBalance, useComplaints, useInvoices, useLeave, useMenu, useNotices, useStudent } from "@/lib/queries";

import { Hero } from "./hero";

const MEAL_ORDER = ["BREAKFAST", "LUNCH", "SNACKS", "DINNER"];
const UNPAID = ["ISSUED", "PARTIALLY_PAID", "OVERDUE"];

export function ResidentHome({ me }: { me: Me }) {
  const student = useStudent(me.student_id);
  const balance = useBalance();
  const invoices = useInvoices({ limit: 20 });
  const menu = useMenu();
  const notices = useNotices();
  const complaints = useComplaints({ limit: 4 });
  const leave = useLeave({ limit: 3 });

  const nextDue = invoices.data?.items
    .filter((i) => UNPAID.includes(i.status))
    .sort((a, b) => a.due_date.localeCompare(b.due_date))[0];
  const overdue = invoices.data?.items.some((i) => i.status === "OVERDUE");
  const outstanding = Number(balance.data?.outstanding ?? 0);
  const todayMeals = (menu.data ?? [])
    .filter((m) => m.day_of_week === new Date().getDay())
    .sort((a, b) => MEAL_ORDER.indexOf(a.meal_type) - MEAL_ORDER.indexOf(b.meal_type));

  return (
    <>
      <Hero name={me.full_name}>
        <div className="flex flex-wrap items-center gap-3">
          {student.data?.room && (
            <span className="inline-flex h-10 items-center gap-2 rounded-control border border-hairline bg-lake-950/50 px-3 text-ui text-mist">
              <BedDouble aria-hidden className="h-4 w-4 text-stone" />
              {student.data.room}
            </span>
          )}
          <Button variant="primary" icon={MessageSquareWarning} href="/complaints">
            Report a problem
          </Button>
          <Button icon={Luggage} href="/leave">
            Request leave
          </Button>
        </div>
      </Hero>

      <div className="grid gap-5 lg:grid-cols-3">
        <Kpi
          label="Fees outstanding"
          value={balance.data ? <Money value={balance.data.outstanding} whole /> : "—"}
          loading={balance.isPending}
          emphasis={overdue ? "alert" : outstanding > 0 ? "warm" : undefined}
          action={<TextLink href="/fees">Your fees</TextLink>}
          context={
            balance.isError
              ? "Couldn't load your balance."
              : nextDue
                ? `Invoice ${nextDue.invoice_number} is due ${formatDate(nextDue.due_date)}`
                : outstanding > 0
                  ? "Pay at the hostel office. Every charge is listed under your fees."
                  : outstanding < 0
                    ? "You're in credit with the hostel."
                    : "You're all paid up."
          }
        />

        <Panel title="Today in the mess" actions={<TextLink href="/mess">Full menu</TextLink>}>
          {menu.isPending ? (
            <SkeletonLines lines={3} />
          ) : menu.isError ? (
            <p className="text-ui text-laligurans-300">The menu didn’t load.</p>
          ) : todayMeals.length === 0 ? (
            <p className="text-ui text-stone">No meals are listed for {WEEKDAYS[new Date().getDay()]}.</p>
          ) : (
            <ul className="space-y-3">
              {todayMeals.map((m) => (
                <li key={m.meal_type} className="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-3 text-ui">
                  <span className="text-stone">{label(m.meal_type)}</span>
                  <span className="text-snow">
                    {m.items}
                    {m.serving_time && <span className="block text-small text-stone">{m.serving_time}</span>}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Notices" actions={<TextLink href="/notices">All notices</TextLink>}>
          {notices.isPending ? (
            <SkeletonLines lines={3} />
          ) : notices.isError ? (
            <p className="text-ui text-laligurans-300">Notices didn’t load.</p>
          ) : notices.data.length === 0 ? (
            <p className="text-ui text-stone">No notices right now.</p>
          ) : (
            <ul className="space-y-4">
              {notices.data.slice(0, 2).map((n) => (
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

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Panel title="Your complaints" actions={<TextLink href="/complaints">All complaints</TextLink>} flush>
          {complaints.isPending ? (
            <SkeletonLines lines={4} className="p-5" />
          ) : complaints.isError ? (
            <ErrorState error={complaints.error} onRetry={() => complaints.refetch()} />
          ) : complaints.data.items.length === 0 ? (
            <EmptyState
              compact
              icon={MessageSquareWarning}
              title="Nothing reported"
              description="If something in the hostel needs fixing, tell the office here."
            />
          ) : (
            <ul className="rows px-5 pb-2">
              {complaints.data.items.map((c) => (
                <li key={c.id} className="flex items-start justify-between gap-4 py-3.5">
                  <div className="min-w-0">
                    <p className="line-clamp-2 text-ui text-snow">{c.summary ?? c.raw_text}</p>
                    <p className="mt-1 text-small text-stone">Filed {timeAgo(c.created_at)}</p>
                  </div>
                  <EnumPill domain="complaintStatus" value={c.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Your leave" actions={<TextLink href="/leave">All leave</TextLink>} flush>
          {leave.isPending ? (
            <SkeletonLines lines={3} className="p-5" />
          ) : leave.isError ? (
            <ErrorState error={leave.error} onRetry={() => leave.refetch()} />
          ) : leave.data.items.length === 0 ? (
            <EmptyState
              compact
              icon={Luggage}
              title="No leave requested"
              description="Going home or travelling? Request leave before you go."
            />
          ) : (
            <ul className="rows px-5 pb-2">
              {leave.data.items.map((l) => (
                <li key={l.id} className="flex items-start justify-between gap-4 py-3.5">
                  <div className="min-w-0">
                    <p className="text-ui text-snow">{label(l.leave_type)}</p>
                    <p className="mt-1 text-small text-stone">{formatRange(l.from_date, l.to_date)}</p>
                  </div>
                  <EnumPill domain="leaveStatus" value={l.status} />
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <p className="mt-8 flex items-center gap-2 text-small text-stone">
        <MessagesSquare aria-hidden className="h-3.5 w-3.5" />
        <span>
          Questions about rules or your fees? Ask the{" "}
          <Link href="/assistant" className="text-mist underline underline-offset-4 hover:text-snow">
            hostel assistant
          </Link>
          .
        </span>
      </p>
    </>
  );
}
