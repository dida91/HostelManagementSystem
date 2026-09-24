"use client";

import { Lock } from "lucide-react";

import { Button, EmptyState, Panel } from "@/components/ui";
import { type Capability, can } from "@/lib/permissions";
import { useMe } from "@/lib/queries";

/**
 * Renders children only for roles with the capability. Others get a clear
 * explanation instead of a page full of refused requests.
 */
export function Guard({
  capability,
  children,
  title = "This page is for the hostel office",
  description = "Your account can't open it. Everything you need is on your home page.",
  action = { href: "/dashboard", label: "Go to home" },
}: {
  capability: Capability;
  children: React.ReactNode;
  title?: string;
  description?: string;
  action?: { href: string; label: string };
}) {
  const { data: me } = useMe();
  if (!me) return null;
  if (!can(me.role, capability)) {
    return (
      <Panel className="mx-auto mt-10 max-w-xl">
        <EmptyState
          icon={Lock}
          title={title}
          description={description}
          action={<Button href={action.href}>{action.label}</Button>}
        />
      </Panel>
    );
  }
  return <>{children}</>;
}

/** For resident-only pages opened by staff: point them to the office view. */
export function ResidentOnly({
  children,
  officeHref,
  officeLabel,
}: {
  children: React.ReactNode;
  officeHref: string;
  officeLabel: string;
}) {
  return (
    <Guard
      capability="studentArea"
      title="This is the residents' view"
      description="Office accounts manage this from the office pages."
      action={{ href: officeHref, label: officeLabel }}
    >
      {children}
    </Guard>
  );
}
