"use client";

import { clsx } from "@/lib/clsx";

export function Card({
  title,
  children,
  actions,
}: {
  title?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-sm">
      {title && (
        <header className="flex items-center justify-between border-b border-slate-100 px-5 py-3">
          <h2 className="text-sm font-semibold text-slate-700">{title}</h2>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

export function Button({
  children,
  variant = "primary",
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" }) {
  return (
    <button
      {...props}
      className={clsx(
        "rounded-md px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary"
          ? "bg-brand-600 text-white hover:bg-brand-700"
          : "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
        props.className,
      )}
    />
  );
}

const TONE: Record<string, string> = {
  URGENT: "bg-red-100 text-red-800",
  HIGH: "bg-orange-100 text-orange-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  LOW: "bg-slate-100 text-slate-700",
  NEGATIVE: "bg-red-100 text-red-800",
  MIXED: "bg-amber-100 text-amber-800",
  POSITIVE: "bg-emerald-100 text-emerald-800",
  RESOLVED: "bg-emerald-100 text-emerald-800",
  SUBMITTED: "bg-sky-100 text-sky-800",
  TRIAGED: "bg-indigo-100 text-indigo-800",
};

export function Badge({ value }: { value: string | null }) {
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <span
      className={clsx(
        "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
        TONE[value] ?? "bg-slate-100 text-slate-700",
      )}
    >
      {value.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
      {message}
    </p>
  );
}
