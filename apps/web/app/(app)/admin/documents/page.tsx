import type { Metadata } from "next";

import { DocumentsView } from "./view";

export const metadata: Metadata = { title: "Documents" };

export default function DocumentsPage() {
  return <DocumentsView />;
}
