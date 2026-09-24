import { cn } from "@/lib/cn";
import { label, tone, type Tone, type ToneDomain } from "@/lib/labels";

const TONES: Record<Tone, string> = {
  neutral: "bg-lake-700/70 text-mist [--dot:#7A9095]",
  info: "bg-glacier/10 text-glacier-300 [--dot:#7FB7DB]",
  progress: "bg-[#5B8DEF]/[0.13] text-[#AFC6F6] [--dot:#5B8DEF]",
  success: "bg-terrace/[0.13] text-terrace-300 [--dot:#57BD8E]",
  warning: "bg-marigold/[0.13] text-marigold-300 [--dot:#F2B544]",
  danger: "bg-laligurans/[0.15] text-laligurans-300 [--dot:#E5455F]",
};

export function StatusPill({
  tone: t = "neutral",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-[3px] text-small font-medium",
        TONES[t],
        className,
      )}
    >
      <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-[var(--dot)]" />
      {children}
    </span>
  );
}

/** A pill for a backend enum value: label and tone come from lib/labels. */
export function EnumPill({ domain, value }: { domain: ToneDomain; value: string | null | undefined }) {
  if (!value) return <span className="text-stone">—</span>;
  return <StatusPill tone={tone(domain, value)}>{label(value)}</StatusPill>;
}

/** Quiet tag for categories and other non-status values. */
export function Tag({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded-full border border-hairline px-2.5 py-[3px] text-small text-mist",
        className,
      )}
    >
      {children}
    </span>
  );
}
