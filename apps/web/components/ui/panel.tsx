import { cn } from "@/lib/cn";

export function Panel({
  title,
  description,
  actions,
  children,
  className,
  bodyClassName,
  flush,
  as: Tag = "section",
}: {
  title?: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  /** No body padding (tables, lists that run edge to edge). */
  flush?: boolean;
  as?: "section" | "div" | "article";
}) {
  return (
    <Tag className={cn("panel min-w-0", flush && "overflow-hidden", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 px-4 pb-1 pt-4 sm:px-5">
          <div className="min-w-0">
            {title && <h2 className="t-sub text-snow">{title}</h2>}
            {description && <p className="mt-0.5 text-ui text-stone">{description}</p>}
          </div>
          {actions && <div className="flex max-w-full shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn(!flush && "p-4 sm:p-5", flush && !!(title || actions) && "pt-3", bodyClassName)}>
        {children}
      </div>
    </Tag>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-8 flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
      <div className="min-w-0">
        <h1 className="t-title text-balance text-snow">{title}</h1>
        {description && (
          <p className="mt-2 max-w-[62ch] text-body text-mist text-pretty">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 md:shrink-0 md:flex-nowrap">{actions}</div>}
    </header>
  );
}

/** Label/value pairs for detail views. */
export function Details({ items }: { items: [React.ReactNode, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[minmax(0,0.9fr)_minmax(0,1.6fr)] gap-x-4 gap-y-3 text-ui">
      {items.map(([term, value], i) => (
        <div key={i} className="contents">
          <dt className="text-stone">{term}</dt>
          <dd className="min-w-0 break-words text-snow">{value ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
