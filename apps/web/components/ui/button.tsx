"use client";

import type { LucideIcon } from "lucide-react";
import Link from "next/link";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

import { Spinner } from "./spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const BASE =
  "relative inline-flex select-none items-center justify-center gap-2 whitespace-nowrap rounded-control font-medium " +
  "transition duration-quick ease-out active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45 " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-marigold/70 focus-visible:ring-offset-2 focus-visible:ring-offset-lake-950";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-marigold text-marigold-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.35)] hover:bg-marigold-300 hover:shadow-action " +
    "disabled:bg-lake-700 disabled:text-mist disabled:shadow-none disabled:opacity-70",
  secondary:
    "border border-line bg-lake-800 text-snow shadow-edge hover:border-line-strong hover:bg-lake-700",
  ghost: "text-mist hover:bg-lake-800 hover:text-snow",
  danger:
    "bg-laligurans text-snow shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] hover:bg-[#EE5C74]",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-small",
  md: "h-10 px-4 text-ui",
  lg: "h-12 px-5 text-body",
};

const ICON_SIZES: Record<Size, string> = { sm: "h-3.5 w-3.5", md: "h-4 w-4", lg: "h-5 w-5" };

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: LucideIcon;
  href?: string;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "secondary", size = "md", loading, icon: Icon, href, className, children, disabled, ...props },
  ref,
) {
  const classes = cn(BASE, VARIANTS[variant], SIZES[size], className);
  const content = (
    <>
      {loading ? <Spinner className={ICON_SIZES[size]} /> : Icon ? <Icon aria-hidden className={ICON_SIZES[size]} /> : null}
      {children}
    </>
  );
  if (href) {
    return (
      <Link href={href} className={classes}>
        {content}
      </Link>
    );
  }
  return (
    <button ref={ref} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...props}>
      {content}
    </button>
  );
});

export interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: LucideIcon;
  label: string;
  variant?: "ghost" | "secondary";
  size?: "sm" | "md";
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { icon: Icon, label, variant = "ghost", size = "md", className, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        BASE,
        VARIANTS[variant],
        size === "sm" ? "h-8 w-8" : "h-10 w-10",
        "px-0",
        className,
      )}
      {...props}
    >
      <Icon aria-hidden className={size === "sm" ? "h-4 w-4" : "h-[18px] w-[18px]"} />
    </button>
  );
});
