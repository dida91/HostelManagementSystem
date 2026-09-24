import type { Metadata } from "next";

import { NoticesView } from "./view";

export const metadata: Metadata = { title: "Notices" };

export default function NoticesPage() {
  return <NoticesView />;
}
