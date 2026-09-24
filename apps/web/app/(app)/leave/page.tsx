import type { Metadata } from "next";

import { LeaveView } from "./view";

export const metadata: Metadata = { title: "Leave" };

export default function LeavePage() {
  return <LeaveView />;
}
