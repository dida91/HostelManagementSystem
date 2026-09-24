"use client";

import { cn } from "@/lib/cn";
import { useSvgId } from "@/lib/use-svg-id";

/** Machhapuchhre's fishtail summit, the hostel's horizon. */
export function BrandMark({ className }: { className?: string }) {
  const light = useSvgId("brand-light");
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("h-8 w-8", className)}>
      <defs>
        <linearGradient id={light} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F7CF7E" />
          <stop offset="1" stopColor="#F08A76" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill="#12292F" />
      <path d="M4 25 L12.2 11.5 L14.6 15 L18.4 6.5 L28 25 Z" fill={`url(#${light})`} />
      <path d="M18.4 6.5 L20.6 11 L18.9 10.2 L17.2 11.6 Z" fill="#EDF3F2" opacity="0.9" />
      <path d="M4 25 H28" stroke="#7FB7DB" strokeOpacity="0.5" strokeWidth="1.2" />
    </svg>
  );
}

export function Brand({ collapsed }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <BrandMark className="shrink-0" />
      {!collapsed && (
        <div className="min-w-0 leading-tight">
          <p className="t-sub text-snow" style={{ fontStretch: "118%" }}>
            Kutumba
          </p>
          <p className="truncate text-small text-stone">Girls hostel, Pokhara</p>
        </div>
      )}
    </div>
  );
}
