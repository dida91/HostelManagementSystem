"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import type { Me } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { usePrefs, useUI } from "@/lib/store";

import { Brand } from "./brand";
import { isActive, navFor } from "./nav";

function NavList({ me, collapsed, onNavigate }: { me: Me; collapsed?: boolean; onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex-1 space-y-6 overflow-y-auto px-3 py-2">
      {navFor(me.role).map((group, gi) => (
        <div key={group.label ?? gi}>
          {group.label && !collapsed && (
            <p className="mb-1.5 px-3 text-small font-medium text-stone">{group.label}</p>
          )}
          {group.label && collapsed && gi > 0 && <div className="mx-3 mb-3 h-px bg-[var(--hairline)]" />}
          <ul className="space-y-0.5">
            {group.items.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                    className={cn(
                      "group relative flex h-10 items-center gap-3 rounded-control px-3 text-ui transition-colors duration-quick",
                      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60",
                      active
                        ? "bg-lake-800 font-medium text-snow shadow-edge"
                        : "text-mist hover:bg-lake-800/60 hover:text-snow",
                      collapsed && "justify-center px-0",
                    )}
                  >
                    {active && (
                      <span aria-hidden className="absolute left-0 top-2 h-6 w-[3px] rounded-r-full bg-marigold" />
                    )}
                    <item.icon
                      aria-hidden
                      className={cn("h-[18px] w-[18px] shrink-0", active ? "text-marigold" : "text-stone group-hover:text-mist")}
                    />
                    {!collapsed && item.label}
                    {collapsed && <span className="sr-only">{item.label}</span>}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

export function Sidebar({ me }: { me: Me }) {
  const collapsed = usePrefs((s) => s.sidebarCollapsed);
  const setCollapsed = usePrefs((s) => s.setSidebarCollapsed);
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-hairline bg-lake-900/80 lg:flex",
        "transition-[width] duration-slow ease-out",
        collapsed ? "w-[76px]" : "w-[252px]",
      )}
    >
      <div className={cn("flex h-16 items-center px-5", collapsed && "justify-center px-0")}>
        <Link href="/dashboard" aria-label="Kutumba home" className="rounded-control focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60">
          <Brand collapsed={collapsed} />
        </Link>
      </div>
      <NavList me={me} collapsed={collapsed} />
      <div className={cn("border-t border-hairline p-3", collapsed && "flex justify-center")}>
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="flex h-9 items-center gap-2 rounded-control px-3 text-small text-stone transition-colors hover:bg-lake-800/60 hover:text-snow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
        >
          {collapsed ? <PanelLeftOpen aria-hidden className="h-4 w-4" /> : <PanelLeftClose aria-hidden className="h-4 w-4" />}
          {!collapsed && "Collapse"}
        </button>
      </div>
    </aside>
  );
}

/** Off-canvas navigation for narrow screens, on the native <dialog>. */
export function MobileNav({ me }: { me: Me }) {
  const open = useUI((s) => s.mobileNavOpen);
  const setOpen = useUI((s) => s.setMobileNavOpen);
  const ref = useRef<HTMLDialogElement>(null);
  const pathname = usePathname();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  useEffect(() => setOpen(false), [pathname, setOpen]);

  return (
    <dialog
      ref={ref}
      aria-label="Menu"
      onCancel={(e) => {
        e.preventDefault();
        setOpen(false);
      }}
      onClick={(e) => e.target === ref.current && setOpen(false)}
      className="m-0 h-dvh max-h-dvh w-[280px] max-w-[85vw] border-r border-hairline bg-lake-900 p-0 text-snow backdrop:bg-[#061014]/70 open:animate-slide-in-left"
    >
      {open && (
        <div className="flex h-full flex-col">
          <div className="flex h-16 items-center px-5">
            <Brand />
          </div>
          <NavList me={me} onNavigate={() => setOpen(false)} />
        </div>
      )}
    </dialog>
  );
}
