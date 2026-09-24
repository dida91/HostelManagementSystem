import Link from "next/link";

import { cn } from "@/lib/cn";

/** A quiet in-app link, e.g. "All notices" in a panel header. */
export function TextLink({ href, className, children }: { href: string; className?: string; children: React.ReactNode }) {
  return (
    <Link
      href={href}
      className={cn(
        "rounded-sm text-ui text-marigold underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/60",
        className,
      )}
    >
      {children}
    </Link>
  );
}
