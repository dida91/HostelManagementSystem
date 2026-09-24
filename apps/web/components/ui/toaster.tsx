"use client";

import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { cn } from "@/lib/cn";
import { type Toast, useUI } from "@/lib/store";

const ICONS = { success: CheckCircle2, error: TriangleAlert, info: Info };
const EDGE = {
  success: "before:bg-terrace",
  error: "before:bg-laligurans",
  info: "before:bg-glacier",
};

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useUI((s) => s.dismissToast);
  useEffect(() => {
    // Errors stay until dismissed: they usually need reading.
    if (toast.tone === "error") return;
    const timer = window.setTimeout(() => dismiss(toast.id), 4000);
    return () => window.clearTimeout(timer);
  }, [toast, dismiss]);
  const Icon = ICONS[toast.tone];
  return (
    <li
      className={cn(
        "glass relative flex w-full animate-toast-in items-start gap-3 overflow-hidden rounded-menu py-3 pl-4 pr-2 shadow-overlay",
        "before:absolute before:inset-y-0 before:left-0 before:w-[3px]",
        EDGE[toast.tone],
      )}
    >
      <Icon
        aria-hidden
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          toast.tone === "success" && "text-terrace-300",
          toast.tone === "error" && "text-laligurans-300",
          toast.tone === "info" && "text-glacier-300",
        )}
      />
      <div className="min-w-0 flex-1">
        <p className="text-ui font-medium text-snow">{toast.title}</p>
        {toast.description && <p className="mt-0.5 text-small text-mist">{toast.description}</p>}
      </div>
      <button
        type="button"
        aria-label="Dismiss"
        onClick={() => dismiss(toast.id)}
        className="rounded-md p-1 text-stone hover:text-snow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
      >
        <X aria-hidden className="h-4 w-4" />
      </button>
    </li>
  );
}

/**
 * The topmost open dialog layer, if any. An open modal makes the rest of the
 * page inert and paints over it, so toasts must render inside it to be seen,
 * dismissed and announced.
 */
function useTopLayer(): HTMLDialogElement | null {
  const [layer, setLayer] = useState<HTMLDialogElement | null>(null);
  useEffect(() => {
    const update = () => {
      const open = document.querySelectorAll<HTMLDialogElement>("dialog[open][data-layer]");
      setLayer(open.length ? open[open.length - 1] : null);
    };
    update();
    let frame = 0;
    const observer = new MutationObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    });
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["open"] });
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);
  return layer;
}

export function Toaster() {
  const toasts = useUI((s) => s.toasts);
  const layer = useTopLayer();
  const list = (
    <ol
      aria-live="polite"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2 [&>li]:pointer-events-auto"
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </ol>
  );
  return layer ? createPortal(list, layer) : list;
}
