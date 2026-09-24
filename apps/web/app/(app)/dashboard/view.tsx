"use client";

import { Skeleton } from "@/components/ui";
import { isStaff } from "@/lib/permissions";
import { useMe } from "@/lib/queries";

import { OfficeHome } from "./office-home";
import { ResidentHome } from "./resident-home";

export function DashboardView() {
  const { data: me } = useMe();
  if (!me) return <Skeleton className="h-72 w-full rounded-stage" />;
  return isStaff(me.role) ? <OfficeHome me={me} /> : <ResidentHome me={me} />;
}
