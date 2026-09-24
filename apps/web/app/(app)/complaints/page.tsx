import type { Metadata } from "next";

import { ComplaintsView } from "./view";

export const metadata: Metadata = { title: "Complaints" };

export default function ComplaintsPage() {
  return <ComplaintsView />;
}
