/**
 * What each role may do, mirroring the backend's role gates so the UI only
 * offers actions that will succeed. The backend remains the authority: hiding
 * a button is a courtesy, never the security boundary.
 */
import type { Role } from "@/lib/api/types";

const STAFF: Role[] = ["STAFF", "WARDEN", "SUPER_ADMIN"];
const WARDEN: Role[] = ["WARDEN", "SUPER_ADMIN"];

const RULES = {
  staffArea: STAFF,
  studentArea: ["STUDENT"] as Role[],
  // residents
  manageStudents: STAFF,
  studentLifecycle: WARDEN,
  // rooms
  viewRooms: STAFF,
  allocateBeds: STAFF,
  manageRooms: WARDEN,
  // complaints and leave
  triage: STAFF,
  decideLeave: WARDEN,
  // money
  viewFees: STAFF,
  issueInvoices: STAFF,
  recordPayments: STAFF,
  generateInvoices: WARDEN,
  manageFeeStructures: WARDEN,
  // daily life
  editMenu: STAFF,
  manageNotices: WARDEN,
  // knowledge and oversight
  manageDocuments: WARDEN,
  viewAnalytics: STAFF,
  exportReports: STAFF,
  exportPersonalReports: WARDEN,
  viewDeliveries: WARDEN,
} satisfies Record<string, Role[]>;

export type Capability = keyof typeof RULES;

export function can(role: Role | undefined, capability: Capability): boolean {
  return !!role && RULES[capability].includes(role);
}

export function isStaff(role: Role | undefined): boolean {
  return can(role, "staffArea");
}

export function roleLabel(role: Role): string {
  return { STUDENT: "Resident", STAFF: "Staff", WARDEN: "Warden", SUPER_ADMIN: "Administrator" }[
    role
  ];
}
