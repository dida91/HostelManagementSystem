"use client";

import { useCallback, useRef, useState } from "react";

export interface TipState {
  x: number;
  y: number;
  content: React.ReactNode;
}

/**
 * One tooltip per chart, positioned inside the chart's own box. React renders
 * the content, so labels from the API are always escaped as text.
 */
export function useChartTip() {
  const box = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<TipState | null>(null);

  const show = useCallback((target: Element, content: React.ReactNode) => {
    const container = box.current?.getBoundingClientRect();
    const rect = target.getBoundingClientRect();
    if (!container) return;
    setTip({ x: rect.left + rect.width / 2 - container.left, y: rect.top - container.top, content });
  }, []);
  const hide = useCallback(() => setTip(null), []);

  const node = tip ? (
    <div
      role="tooltip"
      style={{ left: tip.x, top: tip.y }}
      className="glass pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[calc(100%+8px)] whitespace-nowrap rounded-control px-3 py-2 text-small shadow-overlay"
    >
      {tip.content}
    </div>
  ) : null;

  return { box, show, hide, node };
}

/** Tooltip body: the value leads, the label follows, keyed by a short line. */
export function TipRow({ color, label, value }: { color: string; label: string; value: string }) {
  return (
    <span className="flex items-center gap-2">
      <span aria-hidden className="h-[2px] w-3 rounded-full" style={{ background: color }} />
      <span className="font-semibold text-snow tabular">{value}</span>
      <span className="text-mist">{label}</span>
    </span>
  );
}
