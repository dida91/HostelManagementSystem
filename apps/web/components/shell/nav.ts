import type { LucideIcon } from "lucide-react";
import {
  BedDouble,
  ChartColumn,
  FileSpreadsheet,
  House,
  Library,
  Luggage,
  Megaphone,
  MessageSquareWarning,
  MessagesSquare,
  Users,
  UtensilsCrossed,
  Wallet,
} from "lucide-react";

import type { Role } from "@/lib/api/types";
import { type Capability, can } from "@/lib/permissions";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  capability?: Capability;
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
}

const RESIDENT: NavGroup[] = [
  {
    items: [
      { href: "/dashboard", label: "Home", icon: House },
      { href: "/complaints", label: "Complaints", icon: MessageSquareWarning },
      { href: "/leave", label: "Leave", icon: Luggage },
      { href: "/fees", label: "Fees", icon: Wallet },
      { href: "/mess", label: "Mess", icon: UtensilsCrossed },
      { href: "/notices", label: "Notices", icon: Megaphone },
      { href: "/assistant", label: "Assistant", icon: MessagesSquare },
    ],
  },
];

const OFFICE: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { href: "/dashboard", label: "Home", icon: House },
      { href: "/admin/analytics", label: "Analytics", icon: ChartColumn, capability: "viewAnalytics" },
    ],
  },
  {
    label: "Residents",
    items: [
      { href: "/admin/students", label: "Students", icon: Users, capability: "manageStudents" },
      { href: "/admin/rooms", label: "Rooms", icon: BedDouble, capability: "viewRooms" },
      { href: "/leave", label: "Leave", icon: Luggage },
    ],
  },
  {
    label: "Daily life",
    items: [
      { href: "/admin/complaints", label: "Complaints", icon: MessageSquareWarning, capability: "triage" },
      { href: "/mess", label: "Mess", icon: UtensilsCrossed },
      { href: "/notices", label: "Notices", icon: Megaphone },
    ],
  },
  {
    label: "Money",
    items: [
      { href: "/admin/fees", label: "Fees", icon: Wallet, capability: "viewFees" },
      { href: "/admin/reports", label: "Reports", icon: FileSpreadsheet, capability: "exportReports" },
    ],
  },
  {
    label: "Knowledge",
    items: [
      { href: "/assistant", label: "Assistant", icon: MessagesSquare },
      { href: "/admin/documents", label: "Documents", icon: Library, capability: "manageDocuments" },
    ],
  },
];

export function navFor(role: Role): NavGroup[] {
  const groups = role === "STUDENT" ? RESIDENT : OFFICE;
  return groups
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.capability || can(role, i.capability)) }))
    .filter((g) => g.items.length > 0);
}

export function isActive(pathname: string, href: string): boolean {
  return href === "/dashboard" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}
