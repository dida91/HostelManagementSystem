"use client";

import { cn } from "@/lib/cn";

export interface TabOption<V extends string> {
  value: V;
  label: string;
  count?: number;
}

/** Segmented control for switching views or filters within a page. */
export function Segmented<V extends string>({
  options,
  value,
  onChange,
  label,
  className,
}: {
  options: TabOption<V>[];
  value: V;
  onChange: (value: V) => void;
  label: string;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className={cn(
        "inline-flex max-w-full gap-0.5 overflow-x-auto rounded-[12px] border border-hairline bg-lake-900 p-1 sm:gap-1",
        className,
      )}
    >
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            role="tab"
            type="button"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "inline-flex h-8 shrink-0 items-center gap-2 rounded-control px-2.5 text-ui transition duration-quick ease-out sm:px-3",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60",
              active ? "bg-lake-700 text-snow shadow-edge" : "text-mist hover:text-snow",
            )}
          >
            {o.label}
            {o.count !== undefined && (
              <span
                className={cn(
                  "rounded-full px-1.5 text-small tabular",
                  active ? "bg-marigold/20 text-marigold-300" : "bg-lake-800 text-stone",
                )}
              >
                {o.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
