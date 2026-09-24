import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/cn";
import { nprAmount } from "@/lib/format";

import { Skeleton } from "./skeleton";

/**
 * A money figure with the currency as a quiet unit. The digits never break; in a
 * narrow tile the unit moves above them rather than the sum splitting in two.
 */
export function Money({ value, whole }: { value: string | number | null | undefined; whole?: boolean }) {
  const amount = nprAmount(value, whole);
  if (amount === "—") return <>—</>;
  return (
    <span>
      <span className="mr-[0.3em] text-[0.5em] font-medium tracking-normal text-mist">NPR</span>
      <span className="whitespace-nowrap">{amount}</span>
    </span>
  );
}

export function Kpi({
  label,
  value,
  context,
  icon: Icon,
  action,
  loading,
  emphasis,
  className,
}: {
  label: string;
  value: React.ReactNode;
  context?: React.ReactNode;
  icon?: LucideIcon;
  /** A link or control on the label row, e.g. "Your fees". */
  action?: React.ReactNode;
  loading?: boolean;
  /** Draws the warm edge: this figure needs attention. */
  emphasis?: "warm" | "alert";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "panel relative overflow-hidden p-4 sm:p-5",
        emphasis === "warm" && "before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-gradient-to-r before:from-transparent before:via-marigold/70 before:to-transparent",
        emphasis === "alert" && "before:absolute before:inset-x-0 before:top-0 before:h-px before:bg-gradient-to-r before:from-transparent before:via-laligurans/80 before:to-transparent",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="text-ui text-mist">{label}</p>
        {action ?? (Icon && <Icon aria-hidden className="h-4 w-4 text-stone" />)}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-10 w-2/3" />
      ) : (
        <p className="t-figure mt-2 text-[34px] leading-[40px] text-snow">{value}</p>
      )}
      {context && !loading && <p className="mt-1 text-small text-stone">{context}</p>}
    </div>
  );
}
