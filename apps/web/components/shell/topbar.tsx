"use client";

import { useQueryClient } from "@tanstack/react-query";
import { LogOut, Menu as MenuIcon, Search, Sparkle, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";

import { Avatar, Menu } from "@/components/ui";
import { api } from "@/lib/api";
import type { Me } from "@/lib/api/types";
import { roleLabel } from "@/lib/permissions";
import { usePrefs, useUI } from "@/lib/store";

import { BrandMark } from "./brand";
import { NotificationBell } from "./notification-bell";

export function Topbar({ me }: { me: Me }) {
  const router = useRouter();
  const qc = useQueryClient();
  const setMobileNav = useUI((s) => s.setMobileNavOpen);
  const setCommand = useUI((s) => s.setCommandOpen);
  const reduceEffects = usePrefs((s) => s.reduceEffects);
  const setReduceEffects = usePrefs((s) => s.setReduceEffects);

  const signOut = async () => {
    try {
      await api.auth.logout();
    } finally {
      // Nothing from this session may be shown to whoever signs in next.
      qc.clear();
      router.replace("/login");
    }
  };

  return (
    <header className="glass sticky top-0 z-30 border-x-0 border-t-0">
      <div className="mx-auto flex h-16 max-w-[1240px] items-center gap-2 px-4 sm:px-8">
        <button
          type="button"
          onClick={() => setMobileNav(true)}
          aria-label="Open menu"
          className="grid h-10 w-10 place-items-center rounded-control text-mist hover:bg-lake-800 hover:text-snow lg:hidden"
        >
          <MenuIcon aria-hidden className="h-5 w-5" />
        </button>
        <BrandMark className="h-7 w-7 lg:hidden" />

        <button
          type="button"
          onClick={() => setCommand(true)}
          className="ml-1 hidden h-10 w-[260px] items-center gap-3 rounded-control border border-hairline bg-lake-900/60 px-3 text-ui text-stone transition-colors hover:border-line hover:text-mist sm:flex"
        >
          <Search aria-hidden className="h-4 w-4" />
          <span className="flex-1 text-left">Go to…</span>
          <kbd className="rounded border border-hairline px-1.5 text-small">Ctrl K</kbd>
        </button>

        <div className="ml-auto flex items-center gap-1">
          <button
            type="button"
            onClick={() => setCommand(true)}
            aria-label="Go to page"
            className="grid h-10 w-10 place-items-center rounded-control text-mist hover:bg-lake-800 hover:text-snow sm:hidden"
          >
            <Search aria-hidden className="h-[18px] w-[18px]" />
          </button>
          <NotificationBell />
          <Menu
            label="Account"
            items={[
              { label: "Account and password", icon: UserRound, onSelect: () => router.push("/account") },
              {
                label: reduceEffects ? "Turn effects back on" : "Reduce effects",
                icon: Sparkle,
                onSelect: () => setReduceEffects(!reduceEffects),
              },
              { label: "Sign out", icon: LogOut, onSelect: signOut },
            ]}
            trigger={(props) => (
              <button
                {...props}
                type="button"
                className="ml-1 flex items-center gap-3 rounded-control py-1 pl-1 pr-2 transition-colors hover:bg-lake-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
              >
                <Avatar name={me.full_name} size="sm" />
                <span className="hidden text-left leading-tight md:block">
                  <span className="block text-ui text-snow">{me.full_name}</span>
                  <span className="block text-small text-stone">{roleLabel(me.role)}</span>
                </span>
              </button>
            )}
          />
        </div>
      </div>
    </header>
  );
}
