import type { Metadata } from "next";

import { TriageView } from "./view";

export const metadata: Metadata = { title: "Complaints" };

export default function TriagePage() {
  return <TriageView />;
}
