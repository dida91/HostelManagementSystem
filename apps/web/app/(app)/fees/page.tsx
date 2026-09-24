import type { Metadata } from "next";

import { FeesView } from "./view";

export const metadata: Metadata = { title: "Fees" };

export default function FeesPage() {
  return <FeesView />;
}
