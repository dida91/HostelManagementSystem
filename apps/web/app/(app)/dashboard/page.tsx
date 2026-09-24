import type { Metadata } from "next";

import { DashboardView } from "./view";

export const metadata: Metadata = { title: "Home" };

export default function DashboardPage() {
  return <DashboardView />;
}
