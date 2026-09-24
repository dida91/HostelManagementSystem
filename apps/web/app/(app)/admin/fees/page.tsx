import type { Metadata } from "next";

import { OfficeFeesView } from "./view";

export const metadata: Metadata = { title: "Fees" };

export default function OfficeFeesPage() {
  return <OfficeFeesView />;
}
