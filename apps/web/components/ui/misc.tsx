"use client";

import { Search, Star, UploadCloud, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { cn } from "@/lib/cn";
import { initials } from "@/lib/format";

const AVATAR_TONES = [
  "bg-[#5B8DEF]/25 text-[#C5D6FA]",
  "bg-terrace/25 text-terrace-300",
  "bg-marigold/20 text-marigold-300",
  "bg-alpenglow/25 text-alpenglow-300",
  "bg-glacier/20 text-glacier-300",
];

export function Avatar({ name, size = "md" }: { name: string; size?: "sm" | "md" | "lg" }) {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return (
    <span
      aria-hidden
      className={cn(
        "grid shrink-0 place-items-center rounded-full font-semibold wdth-110",
        AVATAR_TONES[hash % AVATAR_TONES.length],
        size === "sm" && "h-7 w-7 text-small",
        size === "md" && "h-9 w-9 text-ui",
        size === "lg" && "h-14 w-14 text-heading",
      )}
    >
      {initials(name)}
    </span>
  );
}

/** Value that settles `delay` ms after the last change. */
export function useDebounced<T>(value: T, delay = 300): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return settled;
}

export function SearchInput({
  value,
  onChange,
  placeholder,
  label,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  label: string;
  className?: string;
}) {
  return (
    <div className={cn("relative", className)}>
      <Search aria-hidden className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-stone" />
      <input
        type="search"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="control min-h-10 pl-10 pr-9 [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          aria-label="Clear search"
          onClick={() => onChange("")}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-stone hover:text-snow"
        >
          <X aria-hidden className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

/** 1–5 rating as a radio group of stars. */
export function RatingInput({
  value,
  onChange,
  label,
}: {
  value: number;
  onChange: (value: number) => void;
  label: string;
}) {
  const name = useId();
  const words = ["Poor", "Below par", "Okay", "Good", "Excellent"];
  return (
    <fieldset>
      <legend className="mb-1.5 text-ui font-medium text-snow/90">{label}</legend>
      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <label key={n} className="cursor-pointer rounded-md p-1 focus-within:ring-2 focus-within:ring-marigold/60">
            <input
              type="radio"
              name={name}
              value={n}
              checked={value === n}
              onChange={() => onChange(n)}
              className="sr-only"
            />
            <Star
              aria-hidden
              className={cn(
                "h-7 w-7 transition duration-quick",
                n <= value ? "fill-marigold text-marigold" : "text-lake-500 hover:text-mist",
              )}
            />
            <span className="sr-only">
              {n} — {words[n - 1]}
            </span>
          </label>
        ))}
        <span className={cn("ml-2 text-ui", value ? "text-mist" : "text-stone")}>{value ? words[value - 1] : "Choose a rating"}</span>
      </div>
    </fieldset>
  );
}

export function FileDrop({
  accept,
  file,
  onFile,
  hint,
}: {
  accept: string;
  file: File | null;
  onFile: (file: File | null) => void;
  hint: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const dropped = e.dataTransfer.files?.[0];
        if (dropped) onFile(dropped);
      }}
      className={cn(
        "flex flex-col items-center justify-center gap-2 rounded-panel border border-dashed px-6 py-8 text-center transition duration-quick",
        over ? "border-marigold bg-marigold/5" : "border-line-strong bg-lake-900/60",
      )}
    >
      <UploadCloud aria-hidden className="h-6 w-6 text-stone" />
      {file ? (
        <p className="text-ui text-snow">
          {file.name}{" "}
          <span className="text-stone">({Math.max(1, Math.round(file.size / 1024))} KB)</span>
        </p>
      ) : (
        <p className="text-ui text-mist">Drop a file here, or</p>
      )}
      <button
        type="button"
        onClick={() => input.current?.click()}
        className="text-ui font-medium text-marigold underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60"
      >
        {file ? "Choose a different file" : "choose one"}
      </button>
      <p className="text-small text-stone">{hint}</p>
      <input
        ref={input}
        type="file"
        accept={accept}
        className="sr-only"
        tabIndex={-1}
        onChange={(e) => onFile(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}
