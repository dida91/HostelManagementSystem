"use client";

import { Bell, CheckCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Skeleton } from "@/components/ui";
import type { Notification } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { timeAgo } from "@/lib/format";
import { useMarkAllRead, useMarkRead, useNotifications } from "@/lib/queries";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const router = useRouter();
  const { data, isPending, isError } = useNotifications({ limit: 6 }, true);
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();
  const unread = data?.unread ?? 0;

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!panel.current?.contains(e.target as Node) && !button.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const openItem = (n: Notification) => {
    if (!n.read_at) markRead.mutate(n.id);
    setOpen(false);
    if (n.link) router.push(n.link);
  };

  return (
    <div className="relative">
      <button
        ref={button}
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
        className="relative grid h-10 w-10 place-items-center rounded-control text-mist transition-colors hover:bg-lake-800 hover:text-snow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
      >
        <Bell aria-hidden className="h-[18px] w-[18px]" />
        {unread > 0 && (
          <span className="absolute right-0.5 top-0.5 grid h-[18px] min-w-[18px] place-items-center rounded-full bg-marigold px-1 text-[11px] font-semibold leading-none text-marigold-ink ring-2 ring-lake-900 tabular">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div
          ref={panel}
          role="dialog"
          aria-label="Recent notifications"
          className="glass absolute right-0 top-12 z-40 w-[min(380px,calc(100vw-2rem))] animate-scale-in overflow-hidden rounded-menu shadow-overlay"
        >
          <div className="flex items-center justify-between border-b border-hairline px-4 py-3">
            <p className="t-sub">Notifications</p>
            <button
              type="button"
              disabled={!unread || markAll.isPending}
              onClick={() => markAll.mutate()}
              className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-small text-mist hover:text-snow disabled:opacity-40"
            >
              <CheckCheck aria-hidden className="h-3.5 w-3.5" />
              Mark all read
            </button>
          </div>
          <div className="max-h-[360px] overflow-y-auto">
            {isPending ? (
              <div className="space-y-3 p-4">
                <Skeleton />
                <Skeleton className="w-2/3" />
              </div>
            ) : isError ? (
              <p className="p-4 text-ui text-laligurans-300">Notifications didn’t load.</p>
            ) : data.items.length === 0 ? (
              <p className="p-6 text-center text-ui text-stone">
                You’re all caught up. Updates about your requests will appear here.
              </p>
            ) : (
              <ul className="rows">
                {data.items.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => openItem(n)}
                      className="flex w-full gap-3 px-4 py-3 text-left transition-colors hover:bg-lake-700/40 focus-visible:bg-lake-700/40 focus-visible:outline-none"
                    >
                      <span
                        aria-hidden
                        className={cn("mt-2 h-2 w-2 shrink-0 rounded-full", n.read_at ? "bg-transparent" : "bg-marigold")}
                      />
                      <span className="min-w-0 flex-1">
                        <span className={cn("block truncate text-ui", n.read_at ? "text-mist" : "font-medium text-snow")}>
                          {n.title}
                        </span>
                        <span className="mt-0.5 line-clamp-2 block text-small text-stone">{n.body}</span>
                        <span className="mt-1 block text-small text-stone">{timeAgo(n.created_at)}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <Link
            href="/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-hairline px-4 py-3 text-center text-ui text-marigold hover:bg-lake-700/40"
          >
            See all notifications
          </Link>
        </div>
      )}
    </div>
  );
}
