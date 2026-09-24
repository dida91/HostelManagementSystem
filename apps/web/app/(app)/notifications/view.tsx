"use client";

import { Bell, CheckCheck, MailWarning, RotateCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  Button,
  type Column,
  DataTable,
  EmptyState,
  EnumPill,
  ErrorState,
  PageHeader,
  Pagination,
  Panel,
  Segmented,
  Select,
  SkeletonLines,
  Tag,
} from "@/components/ui";
import type { Delivery, Notification } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatDateTime, timeAgo } from "@/lib/format";
import { label } from "@/lib/labels";
import { can } from "@/lib/permissions";
import { useDeliveries, useMarkAllRead, useMarkRead, useMe, useNotifications, useRetryFailed } from "@/lib/queries";
import { toast } from "@/lib/store";

const PAGE = 15;

function Inbox({ unreadOnly }: { unreadOnly: boolean }) {
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const list = useNotifications({ unread_only: unreadOnly, limit: PAGE, offset });
  const markRead = useMarkRead();

  const open = (n: Notification) => {
    if (!n.read_at) markRead.mutate(n.id);
    if (n.link) router.push(n.link);
  };

  if (list.isPending) return <SkeletonLines lines={6} className="p-5" />;
  if (list.isError) return <ErrorState error={list.error} onRetry={() => list.refetch()} />;
  if (list.data.items.length === 0) {
    return (
      <EmptyState
        icon={Bell}
        title={unreadOnly ? "Nothing unread" : "No notifications yet"}
        description="Decisions on your requests, new invoices and notices will arrive here."
      />
    );
  }
  return (
    <>
      <ul className="rows">
        {list.data.items.map((n) => (
          <li key={n.id}>
            <button
              type="button"
              onClick={() => open(n)}
              className="flex w-full gap-4 px-5 py-4 text-left transition-colors hover:bg-lake-800/60 focus-visible:bg-lake-800/60 focus-visible:outline-none"
            >
              <span aria-hidden className={cn("mt-2 h-2 w-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-marigold")} />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2">
                  <span className={cn("text-ui", n.read_at ? "text-mist" : "font-medium text-snow")}>{n.title}</span>
                  <Tag>{label(n.category)}</Tag>
                  {!n.read_at && <span className="sr-only">Unread.</span>}
                </span>
                <span className="mt-1 block max-w-[70ch] whitespace-pre-wrap text-ui text-mist">{n.body}</span>
                <span className="mt-1.5 block text-small text-stone" title={formatDateTime(n.created_at)}>
                  {timeAgo(n.created_at)}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
      <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} />
    </>
  );
}

function DeliveryLog() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const list = useDeliveries({ status: status || undefined, limit: PAGE, offset });
  const failed = useDeliveries({ status: "FAILED", limit: 1 });
  const retry = useRetryFailed();
  const columns: Column<Delivery>[] = [
    { key: "when", header: "Queued", cell: (d) => <span className="whitespace-nowrap text-mist">{timeAgo(d.created_at)}</span> },
    { key: "channel", header: "Channel", hideBelow: "sm", cell: (d) => <Tag>{label(d.channel)}</Tag> },
    { key: "to", header: "To", cell: (d) => <span className="text-snow">{d.destination}</span> },
    { key: "status", header: "Status", cell: (d) => <EnumPill domain="deliveryStatus" value={d.status} /> },
    { key: "attempts", header: "Tries", align: "right", hideBelow: "sm", cell: (d) => d.attempts },
    {
      key: "detail",
      header: "Detail",
      hideBelow: "md",
      cell: (d) => (
        <span className="line-clamp-2 max-w-[40ch] text-mist">
          {d.last_error ?? (d.sent_at ? `Sent ${formatDateTime(d.sent_at)}` : `Next try ${timeAgo(d.next_attempt_at)}`)}
        </span>
      ),
    },
  ];
  const failedCount = failed.data?.total ?? 0;
  return (
    <Panel
      title="Email and SMS log"
      description="What went out, what's retrying and why anything failed."
      actions={
        <div className="flex items-center gap-2">
          <Select
            aria-label="Filter by status"
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
            className="min-h-9 w-40"
          >
            <option value="">All statuses</option>
            {["PENDING", "SENDING", "SENT", "FAILED"].map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            icon={RotateCw}
            disabled={failedCount === 0}
            loading={retry.isPending}
            onClick={() =>
              retry.mutate(undefined, {
                onSuccess: (r) => toast.success(`${r.requeued} ${r.requeued === 1 ? "message" : "messages"} queued again`),
              })
            }
          >
            Retry failed{failedCount ? ` (${failedCount})` : ""}
          </Button>
        </div>
      }
      flush
    >
      <DataTable
        columns={columns}
        rows={list.data?.items}
        rowKey={(d) => d.id}
        loading={list.isFetching}
        error={list.error}
        onRetry={() => list.refetch()}
        empty={{
          icon: MailWarning,
          title: "No email or SMS in this view",
          description:
            "Email and SMS start once the server is configured with an SMTP server or an SMS provider. In-app notifications always work.",
        }}
        footer={list.data && list.data.total > 0 ? <Pagination total={list.data.total} limit={PAGE} offset={offset} onChange={setOffset} /> : null}
      />
    </Panel>
  );
}

export function NotificationsView() {
  const { data: me } = useMe();
  const [tab, setTab] = useState<"all" | "unread" | "log">("all");
  const summary = useNotifications({ limit: 6 }, true);
  const markAll = useMarkAllRead();
  const unread = summary.data?.unread ?? 0;
  return (
    <>
      <PageHeader
        title="Notifications"
        description="Updates about your requests, bills and notices."
        actions={
          tab !== "log" && (
            <Button
              icon={CheckCheck}
              disabled={!unread}
              loading={markAll.isPending}
              onClick={() => markAll.mutate(undefined, { onSuccess: () => toast.success("All marked as read") })}
            >
              Mark all read
            </Button>
          )
        }
      />
      <Segmented
        className="mb-4"
        label="Notification views"
        value={tab}
        onChange={setTab}
        options={[
          { value: "all", label: "All" },
          { value: "unread", label: "Unread", count: unread },
          ...(can(me?.role, "viewDeliveries") ? [{ value: "log" as const, label: "Email and SMS log" }] : []),
        ]}
      />
      {tab === "log" ? (
        <DeliveryLog />
      ) : (
        <Panel flush>
          <Inbox key={tab} unreadOnly={tab === "unread"} />
        </Panel>
      )}
    </>
  );
}
