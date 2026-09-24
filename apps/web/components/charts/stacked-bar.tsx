"use client";

import { TipRow, useChartTip } from "./tooltip";

export interface Segment {
  key: string;
  label: string;
  value: number;
  color: string;
}

/**
 * Part-to-whole as one horizontal bar. Segments are separated by a 2px surface
 * gap (no strokes), square at the baseline, rounded at the data end. The legend
 * carries every value, so the tooltip only adds the share.
 */
export function StackedBar({ segments, title }: { segments: Segment[]; title: string }) {
  const { box, show, hide, node } = useChartTip();
  const total = segments.reduce((s, x) => s + x.value, 0);
  const visible = segments.filter((s) => s.value > 0);
  return (
    <div ref={box} className="relative">
      <div role="img" aria-label={`${title}: ${segments.map((s) => `${s.label} ${s.value}`).join(", ")}`} className="flex h-4 gap-[2px]">
        {visible.map((s, i) => (
          <span
            key={s.key}
            tabIndex={0}
            onPointerEnter={(e) =>
              show(e.currentTarget, <TipRow color={s.color} value={String(s.value)} label={`${s.label}, ${Math.round((s.value / total) * 100)}%`} />)
            }
            onPointerLeave={hide}
            onFocus={(e) =>
              show(e.currentTarget, <TipRow color={s.color} value={String(s.value)} label={`${s.label}, ${Math.round((s.value / total) * 100)}%`} />)
            }
            onBlur={hide}
            className="h-full outline-none transition-[filter] duration-quick hover:brightness-125 focus-visible:ring-2 focus-visible:ring-marigold/60"
            style={{
              flexGrow: s.value,
              flexBasis: 0,
              minWidth: 4,
              background: s.color,
              borderRadius: i === visible.length - 1 ? "0 4px 4px 0" : 0,
            }}
          />
        ))}
        {total === 0 && <span className="h-full flex-1 rounded-r-[4px] bg-lake-700" />}
      </div>
      <ul className="mt-4 flex flex-wrap gap-x-5 gap-y-2">
        {segments.map((s) => (
          <li key={s.key} className="flex items-center gap-2 text-ui">
            <span aria-hidden className="h-2.5 w-2.5 rounded-[3px]" style={{ background: s.color }} />
            <span className="text-mist">{s.label}</span>
            <span className="font-medium text-snow tabular">{s.value}</span>
          </li>
        ))}
      </ul>
      {node}
    </div>
  );
}
