"use client";

import { Search, X } from "lucide-react";
import { useId, useState } from "react";

import { Avatar, Spinner, useDebounced } from "@/components/ui";
import type { Student } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { useStudents } from "@/lib/queries";

/**
 * Search-as-you-type resident picker (combobox). Searches name, email and
 * student code on the server; `filter` narrows results (e.g. no bed yet).
 */
export function StudentPicker({
  value,
  onChange,
  id,
  filter,
  emptyHint = "No resident matches that search.",
  invalid,
}: {
  value: Student | null;
  onChange: (student: Student | null) => void;
  id: string;
  filter?: (student: Student) => boolean;
  emptyHint?: string;
  invalid?: boolean;
}) {
  const listId = useId();
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const q = useDebounced(query.trim(), 250);
  const results = useStudents({ q: q || undefined, limit: 8 });
  const options = (results.data?.items ?? []).filter((s) => !filter || filter(s));

  if (value) {
    return (
      <div className="flex min-h-11 items-center gap-3 rounded-control border border-line bg-[#0B1C22] px-3 py-2">
        <Avatar name={value.full_name} size="sm" />
        <div className="min-w-0 flex-1 leading-tight">
          <p className="truncate text-ui text-snow">{value.full_name}</p>
          <p className="truncate text-small text-stone">
            {value.student_code}
            {value.room ? `, ${value.room}` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onChange(null)}
          aria-label="Choose a different resident"
          className="rounded-md p-1.5 text-stone hover:text-snow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
        >
          <X aria-hidden className="h-4 w-4" />
        </button>
      </div>
    );
  }

  const pick = (s: Student | undefined) => {
    if (!s) return;
    onChange(s);
    setQuery("");
    setOpen(false);
  };

  return (
    <div className="relative">
      <Search aria-hidden className="pointer-events-none absolute left-3.5 top-[22px] h-4 w-4 -translate-y-1/2 text-stone" />
      <input
        id={id}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-invalid={invalid || undefined}
        aria-activedescendant={open && options[active] ? `${listId}-${active}` : undefined}
        autoComplete="off"
        value={query}
        placeholder="Search by name, email or code"
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
          setActive(0);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setOpen(true);
            setActive((i) => Math.min(i + 1, options.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter" && open) {
            e.preventDefault();
            pick(options[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
        className="control pl-10"
      />
      {open && (
        <ul
          id={listId}
          role="listbox"
          className="glass absolute inset-x-0 top-full z-20 mt-1.5 max-h-72 overflow-y-auto rounded-menu p-1.5 shadow-overlay"
        >
          {results.isFetching && options.length === 0 ? (
            <li className="flex items-center gap-2 px-3 py-3 text-ui text-stone">
              <Spinner /> Searching…
            </li>
          ) : options.length === 0 ? (
            <li className="px-3 py-3 text-ui text-stone">{emptyHint}</li>
          ) : (
            options.map((s, i) => (
              <li
                key={s.id}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                onMouseDown={(e) => e.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => pick(s)}
                className={cn(
                  "flex cursor-pointer items-center gap-3 rounded-control px-3 py-2",
                  i === active ? "bg-lake-700/70" : "",
                )}
              >
                <Avatar name={s.full_name} size="sm" />
                <span className="min-w-0 leading-tight">
                  <span className="block truncate text-ui text-snow">{s.full_name}</span>
                  <span className="block truncate text-small text-stone">
                    {s.student_code}
                    {s.room ? `, ${s.room}` : ", no bed"}
                  </span>
                </span>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}
