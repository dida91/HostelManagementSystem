import type { Metadata } from "next";

import { MessView } from "./view";

export const metadata: Metadata = { title: "Mess" };

export default function MessPage() {
  return <MessView />;
}
