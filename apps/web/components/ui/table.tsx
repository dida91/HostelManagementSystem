"use client";

import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

import { cn } from "@/lib/cn";

import { Skeleton } from "./skeleton";
import { EmptyState, ErrorState } from "./states";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  cell: (row: T) => React.ReactNode;
  align?: "left" | "right";
  className?: string;
  /** Hide on narrow screens; the column's content must be available elsewhere. */
  hideBelow?: "sm" | "md" | "lg";
}

const HIDE: Record<NonNullable<Column<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
};

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  error,
  onRetry,
  empty,
  onRowClick,
  selectedKey,
  rowLabel,
  footer,
  skeletonRows = 6,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string;
  loading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  empty?: { icon?: LucideIcon; title: string; description?: React.ReactNode; action?: React.ReactNode };
  onRowClick?: (row: T) => void;
  selectedKey?: string | null;
  /** Accessible name for a clickable row. */
  rowLabel?: (row: T) => string;
  footer?: React.ReactNode;
  skeletonRows?: number;
}) {
  if (error && !rows?.length) return <ErrorState error={error} onRetry={onRetry} />;

  const showSkeleton = loading && !rows;
  if (!showSkeleton && rows && rows.length === 0 && empty) {
    return (
      <EmptyState
        icon={empty.icon ?? Inbox}
        title={empty.title}
        description={empty.description}
        action={empty.action}
      />
    );
  }

  return (
    <div>
      <div className="relative overflow-x-auto">
        <table className="w-full border-collapse text-left text-ui wdth-95">
          <thead>
            <tr className="sunken">
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  className={cn(
                    "whitespace-nowrap px-3 py-2.5 text-small font-medium text-mist first:pl-4 last:pr-4 sm:px-4 sm:first:pl-5 sm:last:pr-5",
                    c.align === "right" && "text-right",
                    c.hideBelow && HIDE[c.hideBelow],
                  )}
                >
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className={cn(loading && rows && "opacity-60 transition-opacity")}>
            {showSkeleton
              ? Array.from({ length: skeletonRows }, (_, i) => (
                  <tr key={i} className="border-t border-hairline">
                    {columns.map((c) => (
                      <td key={c.key} className={cn("px-3 py-4 first:pl-4 last:pr-4 sm:px-4 sm:first:pl-5 sm:last:pr-5", c.hideBelow && HIDE[c.hideBelow])}>
                        <Skeleton className={i % 2 ? "w-3/4" : "w-1/2"} />
                      </td>
                    ))}
                  </tr>
                ))
              : rows?.map((row) => {
                  const key = rowKey(row);
                  const selected = selectedKey === key;
                  return (
                    <tr
                      key={key}
                      onClick={onRowClick ? () => onRowClick(row) : undefined}
                      onKeyDown={
                        onRowClick
                          ? (e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                onRowClick(row);
                              }
                            }
                          : undefined
                      }
                      tabIndex={onRowClick ? 0 : undefined}
                      aria-label={onRowClick && rowLabel ? rowLabel(row) : undefined}
                      aria-selected={onRowClick ? selected : undefined}
                      className={cn(
                        "border-t border-hairline align-middle transition-colors duration-quick",
                        onRowClick && "cursor-pointer hover:bg-lake-800/70 focus-visible:bg-lake-800/70 focus-visible:outline-none",
                        selected && "bg-lake-800 shadow-[inset_3px_0_0_#F2B544]",
                      )}
                    >
                      {columns.map((c) => (
                        <td
                          key={c.key}
                          className={cn(
                            "px-3 py-3.5 first:pl-4 last:pr-4 sm:px-4 sm:first:pl-5 sm:last:pr-5",
                            c.align === "right" && "text-right tabular",
                            c.hideBelow && HIDE[c.hideBelow],
                            c.className,
                          )}
                        >
                          {c.cell(row)}
                        </td>
                      ))}
                    </tr>
                  );
                })}
          </tbody>
        </table>
      </div>
      {footer}
    </div>
  );
}
