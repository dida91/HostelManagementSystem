"use client";

import type { LucideIcon } from "lucide-react";
import { Lock, RotateCw, WifiOff, TriangleAlert } from "lucide-react";

import { ApiError } from "@/lib/api/client";
import { cn } from "@/lib/cn";

import { Button } from "./button";

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  compact,
}: {
  icon: LucideIcon;
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
  /** Tighter spacing for empty lists inside smaller panels. */
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center px-6 text-center", compact ? "py-8" : "py-12", className)}>
      <span className="mb-4 grid h-12 w-12 place-items-center rounded-full border border-hairline bg-lake-900 text-stone">
        <Icon aria-hidden className="h-5 w-5" />
      </span>
      <p className="t-sub text-snow">{title}</p>
      {description && <p className="mt-1 max-w-[46ch] text-ui text-stone text-pretty">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/** Explain a failed request in plain words, with a retry where it can help. */
export function ErrorState({
  error,
  onRetry,
  className,
}: {
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const status = error instanceof ApiError ? error.status : undefined;
  const forbidden = status === 403;
  const offline = status === 0;
  const Icon = forbidden ? Lock : offline ? WifiOff : TriangleAlert;
  const title = forbidden
    ? "Not available for your account"
    : offline
      ? "Can't reach the server"
      : "This didn't load";
  const message =
    error instanceof ApiError
      ? error.message
      : "Something unexpected happened while loading this.";
  return (
    <div role="alert" className={cn("flex flex-col items-center px-6 py-10 text-center", className)}>
      <span
        className={cn(
          "mb-4 grid h-12 w-12 place-items-center rounded-full border",
          forbidden
            ? "border-hairline bg-lake-900 text-stone"
            : "border-laligurans/30 bg-laligurans/10 text-laligurans-300",
        )}
      >
        <Icon aria-hidden className="h-5 w-5" />
      </span>
      <p className="t-sub text-snow">{title}</p>
      <p className="mt-1 max-w-[48ch] text-ui text-stone">{message}</p>
      {onRetry && !forbidden && (
        <Button className="mt-5" size="sm" icon={RotateCw} onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Inline form-level error (for failed submissions). */
export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof ApiError ? error.message : "That didn't work. Try again.";
  return (
    <p
      role="alert"
      className="flex items-start gap-2 rounded-control border border-laligurans/30 bg-laligurans/10 px-3 py-2.5 text-ui text-laligurans-300"
    >
      <TriangleAlert aria-hidden className="mt-0.5 h-4 w-4 shrink-0" />
      {message}
    </p>
  );
}

/** Field errors from a 422 response, keyed by field name. */
export function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError ? error.fields : {};
}
