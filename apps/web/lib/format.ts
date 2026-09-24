/**
 * Display formatting. Figures arrive computed from the backend; these helpers
 * only present them. Nepal groups digits the South Asian way (1,23,456.00).
 */

const money = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const moneyWhole = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const dayMonth = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });
const relative = new Intl.RelativeTimeFormat("en", { numeric: "auto" });

/** The amount alone, grouped the South Asian way; "—" when missing. */
export function nprAmount(value: string | number | null | undefined, whole = false): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return "—";
  return (whole ? moneyWhole : money).format(n);
}

export function npr(value: string | number | null | undefined, whole = false): string {
  const amount = nprAmount(value, whole);
  return amount === "—" ? amount : `NPR ${amount}`;
}

/** A duration in hours, readable at a glance: under an hour, hours, then days. */
export function formatHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined || !Number.isFinite(hours)) return "—";
  if (hours < 1) return "Under 1 h";
  if (hours < 48) return `${Math.round(hours * 10) / 10} h`;
  return `${Math.round((hours / 24) * 10) / 10} days`;
}

/** Parse "YYYY-MM-DD" as a local calendar date (not UTC midnight). */
function parseDay(value: string): Date {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

function toDate(value: string | Date): Date {
  if (value instanceof Date) return value;
  return /^\d{4}-\d{2}-\d{2}$/.test(value) ? parseDay(value) : new Date(value);
}

export function formatDate(value: string | Date | null | undefined): string {
  return value ? dateFmt.format(toDate(value)) : "—";
}

export function formatDayMonth(value: string | Date | null | undefined): string {
  return value ? dayMonth.format(toDate(value)) : "—";
}

export function formatDateTime(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const d = toDate(value);
  return `${dateFmt.format(d)}, ${timeFmt.format(d)}`;
}

export function formatRange(from: string, to: string): string {
  return from === to ? formatDate(from) : `${formatDayMonth(from)} – ${formatDate(to)}`;
}

/** "3 hours ago", "yesterday", "in 2 days". */
export function timeAgo(value: string | Date | null | undefined): string {
  if (!value) return "—";
  const seconds = (toDate(value).getTime() - Date.now()) / 1000;
  const abs = Math.abs(seconds);
  if (abs < 45) return "just now";
  const units: [Intl.RelativeTimeFormatUnit, number][] = [
    ["minute", 60],
    ["hour", 3600],
    ["day", 86400],
    ["week", 604800],
    ["month", 2629800],
    ["year", 31557600],
  ];
  let unit: [Intl.RelativeTimeFormatUnit, number] = units[0];
  for (const u of units) if (abs >= u[1]) unit = u;
  return relative.format(Math.round(seconds / unit[1]), unit[0]);
}

/** Today's date in the user's local calendar, as YYYY-MM-DD. */
export function todayISO(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toLocaleDateString("en-CA");
}

/** "2026-10" for the current local month. */
export function currentPeriod(): string {
  return todayISO().slice(0, 7);
}

/** Billing months, newest first: `ahead` months past this one, then back `count` in total. */
export function recentPeriods(count = 13, ahead = 1): string[] {
  const [y, m] = currentPeriod().split("-").map(Number);
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(y, m - 1 + ahead - i, 1);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
}

export function periodLabel(period: string): string {
  const [y, m] = period.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" }).format(
    new Date(y, m - 1, 1),
  );
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parseDay(to).getTime() - parseDay(from).getTime()) / 86400000) + 1;
}

export const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function greeting(date = new Date()): string {
  const h = date.getHours();
  if (h < 5) return "Hello";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
