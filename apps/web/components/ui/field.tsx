"use client";

import { AlertCircle, ChevronDown } from "lucide-react";
import { forwardRef } from "react";

import { cn } from "@/lib/cn";

export function Field({
  label,
  htmlFor,
  help,
  error,
  required,
  className,
  children,
}: {
  label: React.ReactNode;
  htmlFor: string;
  help?: React.ReactNode;
  error?: string | null;
  required?: boolean;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("space-y-1.5", className)}>
      <label htmlFor={htmlFor} className="block text-ui font-medium text-snow/90">
        {label}
        {required && (
          <span className="ml-0.5 text-marigold" aria-hidden>
            *
          </span>
        )}
      </label>
      {children}
      {error ? (
        <p id={`${htmlFor}-error`} className="flex items-start gap-1.5 text-small text-laligurans-300">
          <AlertCircle aria-hidden className="mt-px h-3.5 w-3.5 shrink-0" />
          {error}
        </p>
      ) : help ? (
        <p id={`${htmlFor}-help`} className="text-small text-stone">
          {help}
        </p>
      ) : null}
    </div>
  );
}

type WithInvalid = { invalid?: boolean };

export const Input = forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement> & WithInvalid>(
  function Input({ className, invalid, id, ...props }, ref) {
    return (
      <input
        ref={ref}
        id={id}
        aria-invalid={invalid || undefined}
        aria-describedby={id ? (invalid ? `${id}-error` : `${id}-help`) : undefined}
        className={cn("control", className)}
        {...props}
      />
    );
  },
);

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement> & WithInvalid
>(function Textarea({ className, invalid, id, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      id={id}
      aria-invalid={invalid || undefined}
      aria-describedby={id ? (invalid ? `${id}-error` : `${id}-help`) : undefined}
      className={cn("control min-h-[104px] resize-y py-2.5 leading-6", className)}
      {...props}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement> & WithInvalid
>(function Select({ className, invalid, children, ...props }, ref) {
  return (
    <div className="relative">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={cn("control cursor-pointer appearance-none pr-10", className)}
        {...props}
      >
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-stone"
      />
    </div>
  );
});

export function Checkbox({
  label,
  description,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & { label: React.ReactNode; description?: string }) {
  return (
    <label className={cn("flex cursor-pointer items-start gap-3 text-ui", className)}>
      <input
        type="checkbox"
        className="mt-0.5 h-[18px] w-[18px] shrink-0 cursor-pointer rounded accent-marigold"
        {...props}
      />
      <span>
        <span className="text-snow">{label}</span>
        {description && <span className="mt-0.5 block text-small text-stone">{description}</span>}
      </span>
    </label>
  );
}

/** Lay out related fields in a responsive grid. */
export function FieldRow({ children, cols = 2 }: { children: React.ReactNode; cols?: 2 | 3 }) {
  return (
    <div className={cn("grid gap-4", cols === 3 ? "sm:grid-cols-3" : "sm:grid-cols-2")}>
      {children}
    </div>
  );
}
