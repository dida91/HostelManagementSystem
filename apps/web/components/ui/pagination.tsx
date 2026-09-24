"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";

import { IconButton } from "./button";

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit && offset === 0) {
    return (
      <p className="border-t border-hairline px-4 py-3 text-small text-stone sm:px-5">
        {total} {total === 1 ? "item" : "items"}
      </p>
    );
  }
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);
  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between gap-3 border-t border-hairline px-4 py-2.5 sm:px-5"
    >
      <p className="text-small text-stone tabular">
        {first}–{last} of {total}
      </p>
      <div className="flex gap-1">
        <IconButton
          icon={ChevronLeft}
          label="Previous page"
          size="sm"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        />
        <IconButton
          icon={ChevronRight}
          label="Next page"
          size="sm"
          disabled={last >= total}
          onClick={() => onChange(offset + limit)}
        />
      </div>
    </nav>
  );
}
