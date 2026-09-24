"use client";

import { CornerDownLeft, Search, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bell } from "lucide-react";

import type { Me } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { useUI } from "@/lib/store";

import { navFor, type NavItem } from "./nav";

/** "Go to…" — keyboard navigation across every page the role can open. */
export function CommandPalette({ me }: { me: Me }) {
  const open = useUI((s) => s.commandOpen);
  const setOpen = useUI((s) => s.setCommandOpen);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const ref = useRef<HTMLDialogElement>(null);
  const router = useRouter();

  const items: NavItem[] = useMemo(
    () => [
      ...navFor(me.role).flatMap((g) => g.items),
      { href: "/notifications", label: "Notifications", icon: Bell },
      { href: "/account", label: "Account and password", icon: UserRound },
    ],
    [me.role],
  );
  const matches = items.filter((i) => i.label.toLowerCase().includes(query.trim().toLowerCase()));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useUI.getState().commandOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setQuery("");
      setIndex(0);
      dialog.showModal();
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const go = (item: NavItem | undefined) => {
    if (!item) return;
    setOpen(false);
    router.push(item.href);
  };

  return (
    <dialog
      ref={ref}
      aria-label="Go to page"
      onCancel={(e) => {
        e.preventDefault();
        setOpen(false);
      }}
      onClick={(e) => e.target === ref.current && setOpen(false)}
      className="glass mx-auto mt-[12vh] w-[calc(100%-2rem)] max-w-[520px] overflow-hidden rounded-overlay p-0 text-snow shadow-overlay backdrop:bg-[#061014]/70 open:animate-scale-in"
    >
      {open && (
        <div>
          <div className="flex items-center gap-3 border-b border-hairline px-4">
            <Search aria-hidden className="h-4 w-4 text-stone" />
            <input
              autoFocus
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setIndex(0);
              }}
              onKeyDown={(e) => {
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setIndex((i) => Math.min(i + 1, matches.length - 1));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setIndex((i) => Math.max(i - 1, 0));
                } else if (e.key === "Enter") {
                  e.preventDefault();
                  go(matches[index]);
                }
              }}
              placeholder="Go to…"
              aria-label="Page name"
              className="h-14 flex-1 bg-transparent text-body text-snow outline-none placeholder:text-stone"
            />
            <kbd className="rounded border border-hairline px-1.5 text-small text-stone">Esc</kbd>
          </div>
          <ul role="listbox" aria-label="Pages" className="max-h-[320px] overflow-y-auto p-2">
            {matches.length === 0 && <li className="px-3 py-6 text-center text-ui text-stone">No page by that name.</li>}
            {matches.map((item, i) => (
              <li key={item.href} role="option" aria-selected={i === index}>
                <button
                  type="button"
                  onMouseEnter={() => setIndex(i)}
                  onClick={() => go(item)}
                  className={cn(
                    "flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-left text-ui",
                    i === index ? "bg-lake-700/70 text-snow" : "text-mist",
                  )}
                >
                  <item.icon aria-hidden className={cn("h-4 w-4", i === index ? "text-marigold" : "text-stone")} />
                  <span className="flex-1">{item.label}</span>
                  {i === index && <CornerDownLeft aria-hidden className="h-3.5 w-3.5 text-stone" />}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </dialog>
  );
}
