"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef } from "react";

import { cn } from "@/lib/cn";

import { Button, IconButton } from "./button";

// Overlays stack (a confirm over a drawer), so the page scroll lock is counted.
let scrollLocks = 0;

function useDialog(open: boolean) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog || !open) return;
    if (!dialog.open) dialog.showModal();
    if (scrollLocks++ === 0) document.documentElement.style.overflow = "hidden";
    return () => {
      if (--scrollLocks === 0) document.documentElement.style.overflow = "";
      if (dialog.open) dialog.close();
    };
  }, [open]);
  // Titles and descriptions are per instance: stacked overlays must not share ids.
  const titleId = useId();
  const descriptionId = useId();
  return { ref, titleId, descriptionId };
}

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** While true, Esc and backdrop clicks do nothing (e.g. saving). */
  busy?: boolean;
}

/**
 * The <dialog> itself is a bare full-screen layer; the visible panel sits inside.
 * Nothing on the dialog transforms or filters, so anything rendered into an open
 * layer (toasts, menus) positions against the viewport as usual. Only content
 * inside the open dialog is interactive: the rest of the page is inert.
 */
const LAYER =
  "m-0 h-full max-h-none w-full max-w-none overflow-hidden border-0 bg-transparent p-0 text-snow open:flex";

/** Centred modal on the native <dialog> (focus trap, Esc, inert background). */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  busy,
  size = "md",
}: OverlayProps & { size?: "md" | "lg" }) {
  const { ref, titleId, descriptionId } = useDialog(open);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !busy) onClose();
      }}
      data-layer=""
      className={cn(LAYER, "items-center justify-center backdrop:bg-[#061014]/75 backdrop:backdrop-blur-[2px]")}
    >
      {open && (
        <div
          className={cn(
            "glass flex max-h-[min(88dvh,900px)] w-[calc(100%-2rem)] animate-scale-in flex-col overflow-hidden rounded-overlay shadow-overlay",
            size === "lg" ? "max-w-[760px]" : "max-w-[560px]",
          )}
        >
          <header className="flex items-start justify-between gap-4 px-6 pb-2 pt-5">
            <div>
              <h2 id={titleId} className="t-heading">
                {title}
              </h2>
              {description && (
                <p id={descriptionId} className="mt-1 text-ui text-mist">
                  {description}
                </p>
              )}
            </div>
            <IconButton icon={X} label="Close" size="sm" onClick={onClose} disabled={busy} />
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>
          {footer && (
            <footer className="flex flex-wrap justify-end gap-2 border-t border-hairline px-6 py-4">
              {footer}
            </footer>
          )}
        </div>
      )}
    </dialog>
  );
}

/** Right-hand sheet for details and edits, keeping the list in view. */
export function Drawer({ open, onClose, title, description, children, footer, busy }: OverlayProps) {
  const { ref, titleId } = useDialog(open);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current && !busy) onClose();
      }}
      data-layer=""
      className={cn(LAYER, "justify-end backdrop:bg-[#061014]/65")}
    >
      {open && (
        <div className="glass flex h-full w-full max-w-[540px] animate-slide-in-right flex-col overflow-hidden rounded-none border-y-0 border-r-0 shadow-overlay sm:rounded-l-overlay">
          <header className="flex items-start justify-between gap-4 border-b border-hairline px-6 py-5">
            <div className="min-w-0">
              <h2 id={titleId} className="t-heading truncate">
                {title}
              </h2>
              {description && <div className="mt-1 text-ui text-mist">{description}</div>}
            </div>
            <IconButton icon={X} label="Close" size="sm" onClick={onClose} disabled={busy} />
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">{children}</div>
          {footer && (
            <footer className="flex flex-wrap justify-end gap-2 border-t border-hairline px-6 py-4">
              {footer}
            </footer>
          )}
        </div>
      )}
    </dialog>
  );
}

/** Confirmation for consequential actions. Names the object and the outcome. */
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  children,
  confirmLabel,
  tone = "primary",
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  children?: React.ReactNode;
  confirmLabel: string;
  tone?: "primary" | "danger";
  loading?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      busy={loading}
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant={tone} loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-body text-mist">{children}</div>
    </Modal>
  );
}
