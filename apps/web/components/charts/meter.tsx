import { SERIES_1, TRACK_SKY } from "./palette";

/** A single ratio against its limit (beds filled, fees collected). */
export function Meter({
  label,
  value,
  max,
  display,
  caption,
}: {
  label: string;
  value: number;
  max: number;
  display: string;
  caption?: string;
}) {
  const pct = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-ui text-mist">{label}</span>
        <span className="text-ui font-medium text-snow tabular">{display}</span>
      </div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={display}
        className="mt-2 h-2 overflow-hidden rounded-full"
        style={{ background: TRACK_SKY }}
      >
        <div className="h-full rounded-r-[4px]" style={{ width: `${pct * 100}%`, background: SERIES_1 }} />
      </div>
      {caption && <p className="mt-1.5 text-small text-stone">{caption}</p>}
    </div>
  );
}
