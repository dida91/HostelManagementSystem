"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { ErrorState, Skeleton } from "@/components/ui";
import { api, onSessionExpired } from "@/lib/api";
import { useMe } from "@/lib/queries";

import { CommandPalette } from "./command-palette";
import { MobileNav, Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const qc = useQueryClient();
  const me = useMe();

  useEffect(
    () =>
      onSessionExpired(() => {
        qc.clear();
        // Clear the stale cookies so the next sign-in starts clean.
        api.auth.logout().catch(() => undefined);
        router.replace("/login?expired=1");
      }),
    [qc, router],
  );

  if (me.isPending) {
    return (
      <div className="flex min-h-dvh" aria-busy="true">
        <div className="hidden w-[252px] border-r border-hairline bg-lake-900/80 lg:block" />
        <div className="flex-1 px-4 pt-24 sm:px-8">
          <div className="mx-auto max-w-[1240px] space-y-4">
            <Skeleton className="h-10 w-72" />
            <Skeleton className="h-5 w-96 max-w-full" />
            <Skeleton className="mt-8 h-48 w-full rounded-panel" />
          </div>
        </div>
      </div>
    );
  }

  if (me.isError || !me.data) {
    return (
      <div className="grid min-h-dvh place-items-center px-4">
        <ErrorState error={me.error} onRetry={() => me.refetch()} />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-control focus:bg-marigold focus:px-4 focus:py-2 focus:text-marigold-ink"
      >
        Skip to content
      </a>
      <Sidebar me={me.data} />
      <MobileNav me={me.data} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar me={me.data} />
        <main id="main" className="mx-auto w-full max-w-[1240px] flex-1 px-4 pb-20 pt-8 sm:px-8 sm:pt-10">
          {children}
        </main>
      </div>
      <CommandPalette me={me.data} />
    </div>
  );
}
