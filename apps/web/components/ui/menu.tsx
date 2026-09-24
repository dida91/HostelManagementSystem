"use client";

import type { LucideIcon } from "lucide-react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";

export interface MenuItem {
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  tone?: "danger";
  disabled?: boolean;
}

/**
 * Dropdown menu. Rendered in a portal so it is never clipped by a scrolling
 * table. Inside a modal <dialog> (a drawer) it renders within the dialog, since
 * everything outside an open modal is inert. Arrow keys move, Enter selects,
 * Esc closes.
 */
export function Menu({
  trigger,
  items,
  align = "end",
  label,
}: {
  trigger: (props: {
    ref: React.Ref<HTMLButtonElement>;
    onClick: () => void;
    "aria-expanded": boolean;
    "aria-haspopup": "menu";
  }) => React.ReactNode;
  items: MenuItem[];
  align?: "start" | "end";
  label: string;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; container: Element | null } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const close = useCallback((refocus = true) => {
    setOpen(false);
    if (refocus) triggerRef.current?.focus();
  }, []);

  useLayoutEffect(() => {
    if (!open || !triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const dialog = triggerRef.current.closest("dialog");
    const frame = dialog?.getBoundingClientRect() ?? { top: 0, left: 0, width: window.innerWidth };
    const width = 220;
    const left = (align === "end" ? rect.right - width : rect.left) - frame.left;
    setPos({
      top: rect.bottom + 6 - frame.top,
      left: Math.max(8, Math.min(left, frame.width - width - 8)),
      container: dialog,
    });
  }, [open, align]);

  useEffect(() => {
    if (!open) return;
    const first = menuRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)");
    first?.focus();
    const onDown = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node) && !triggerRef.current?.contains(e.target as Node)) {
        close(false);
      }
    };
    const onScroll = () => close(false);
    document.addEventListener("mousedown", onDown);
    window.addEventListener("resize", onScroll);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("resize", onScroll);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [open, close]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const buttons = Array.from(
      menuRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [],
    );
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      buttons[(index + 1) % buttons.length]?.focus();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      buttons[(index - 1 + buttons.length) % buttons.length]?.focus();
    } else if (e.key === "Escape" || e.key === "Tab") {
      e.preventDefault();
      close();
    }
  };

  return (
    <>
      {trigger({
        ref: triggerRef,
        onClick: () => setOpen((v) => !v),
        "aria-expanded": open,
        "aria-haspopup": "menu",
      })}
      {open &&
        pos &&
        createPortal(
          <div
            ref={menuRef}
            role="menu"
            aria-label={label}
            onKeyDown={onKeyDown}
            style={{ top: pos.top, left: pos.left, width: 220 }}
            className={cn(
              "glass z-50 animate-scale-in rounded-menu p-1.5 shadow-overlay",
              pos.container ? "absolute" : "fixed",
            )}
          >
            {items.map((item) => (
              <button
                key={item.label}
                role="menuitem"
                type="button"
                disabled={item.disabled}
                onClick={() => {
                  close();
                  item.onSelect();
                }}
                className={cn(
                  "flex w-full items-center gap-2.5 rounded-control px-3 py-2 text-left text-ui transition-colors duration-quick",
                  "focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-40",
                  item.tone === "danger"
                    ? "text-laligurans-300 hover:bg-laligurans/10 focus-visible:bg-laligurans/10"
                    : "text-snow hover:bg-lake-700/70 focus-visible:bg-lake-700/70",
                )}
              >
                {item.icon && <item.icon aria-hidden className="h-4 w-4 shrink-0 opacity-80" />}
                {item.label}
              </button>
            ))}
          </div>,
          pos.container ?? document.body,
        )}
    </>
  );
}
