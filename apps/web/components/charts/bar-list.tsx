"use client";

import { SERIES_1 } from "./palette";
import { TipRow, useChartTip } from "./tooltip";

export interface BarDatum {
  key: string;
  label: string;
  value: number;
}

/**
 * Horizontal bars for one series of nominal categories: slot-1 hue for every
 * bar, sorted, value at the tip. Bars are 12px (never fill the band), square at
 * the baseline with a 4px rounded data end.
 */
export function BarList({
  data,
  title,
  max,
  format = (v) => String(v),
  share = true,
}: {
  data: BarDatum[];
  title: string;
  /** Fixed scale maximum (e.g. 5 for ratings); defaults to the largest value. */
  max?: number;
  format?: (value: number) => string;
  /** Show each bar's share of the total in the tooltip. */
  share?: boolean;
}) {
  const { box, show, hide, node } = useChartTip();
  const total = data.reduce((s, d) => s + d.value, 0);
  const scale = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <div ref={box} className="relative">
      <ul aria-label={title} className="space-y-3">
        {data.map((d) => {
          const pct = Math.max(0, Math.min(1, d.value / scale));
          const tip = (
            <TipRow
              color={SERIES_1}
              value={format(d.value)}
              label={share && total ? `${d.label}, ${Math.round((d.value / total) * 100)}% of ${total}` : d.label}
            />
          );
          return (
            <li
              key={d.key}
              tabIndex={0}
              aria-label={`${d.label}: ${format(d.value)}`}
              onPointerEnter={(e) => show(e.currentTarget.querySelector("[data-bar]") ?? e.currentTarget, tip)}
              onPointerLeave={hide}
              onFocus={(e) => show(e.currentTarget.querySelector("[data-bar]") ?? e.currentTarget, tip)}
              onBlur={hide}
              className="group grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)] items-center gap-3 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-marigold/60 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]"
            >
              <span className="truncate text-ui text-mist">{d.label}</span>
              <span className="flex min-w-0 items-center gap-2.5">
                <span className="relative h-3 min-w-0 flex-1">
                  <span
                    data-bar
                    className="absolute inset-y-0 left-0 rounded-r-[4px] transition-[filter] duration-quick group-hover:brightness-125 group-focus-visible:brightness-125"
                    style={{ width: `max(${pct * 100}%, 2px)`, background: SERIES_1 }}
                  />
                </span>
                <span className="w-12 shrink-0 text-right text-ui font-medium text-snow tabular">
                  {format(d.value)}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      {node}
    </div>
  );
}
