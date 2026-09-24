/**
 * Human labels and status tones for backend enums. Every value has a label;
 * tones follow DESIGN_SYSTEM.md (colour is never the only signal).
 */

export type Tone = "neutral" | "info" | "progress" | "success" | "warning" | "danger";

const SPECIAL: Record<string, string> = {
  HOME_VISIT: "Home visit",
  STAFF_BEHAVIOUR: "Staff behaviour",
  WARDEN_OFFICE: "Warden's office",
  SUPER_ADMIN: "Administrator",
  ESEWA: "eSewa",
  KHALTI: "Khalti",
  BANK_TRANSFER: "Bank transfer",
  IT: "IT",
  FAQ: "FAQ",
  ON_LEAVE: "On leave",
  OUT_OF_SERVICE: "Out of service",
  PARTIALLY_PAID: "Part paid",
  ONE_TIME: "One-time",
  SMS: "SMS",
};

/** "IN_PROGRESS" -> "In progress". */
export function label(value: string | null | undefined): string {
  if (!value) return "—";
  if (SPECIAL[value]) return SPECIAL[value];
  const words = value.toLowerCase().replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

const TONES: Record<string, Record<string, Tone>> = {
  complaintStatus: {
    SUBMITTED: "info",
    TRIAGED: "progress",
    IN_PROGRESS: "progress",
    RESOLVED: "success",
    CLOSED: "neutral",
    REJECTED: "neutral",
  },
  priority: { LOW: "neutral", MEDIUM: "info", HIGH: "warning", URGENT: "danger" },
  leaveStatus: {
    PENDING: "warning",
    APPROVED: "success",
    REJECTED: "danger",
    CANCELLED: "neutral",
    COMPLETED: "neutral",
  },
  invoiceStatus: {
    DRAFT: "neutral",
    ISSUED: "info",
    PARTIALLY_PAID: "progress",
    PAID: "success",
    OVERDUE: "danger",
    VOID: "neutral",
  },
  sentiment: { POSITIVE: "success", NEUTRAL: "neutral", NEGATIVE: "danger", MIXED: "warning" },
  roomStatus: { AVAILABLE: "success", FULL: "info", MAINTENANCE: "warning", CLOSED: "neutral" },
  bedStatus: {
    VACANT: "success",
    OCCUPIED: "info",
    RESERVED: "warning",
    OUT_OF_SERVICE: "neutral",
  },
  studentStatus: {
    ACTIVE: "success",
    PROSPECTIVE: "info",
    ON_LEAVE: "warning",
    ALUMNI: "neutral",
    SUSPENDED: "danger",
  },
  documentStatus: {
    UPLOADED: "info",
    PROCESSING: "progress",
    INDEXED: "success",
    FAILED: "danger",
    ARCHIVED: "neutral",
  },
  deliveryStatus: { PENDING: "info", SENDING: "progress", SENT: "success", FAILED: "danger" },
};

export type ToneDomain = keyof typeof TONES;

export function tone(domain: ToneDomain, value: string | null | undefined): Tone {
  return (value && TONES[domain][value]) || "neutral";
}

export const OPTIONS = {
  complaintCategory: [
    "WATER",
    "ELECTRICITY",
    "INTERNET",
    "CLEANLINESS",
    "FOOD",
    "MAINTENANCE",
    "SECURITY",
    "NOISE",
    "HARASSMENT",
    "STAFF_BEHAVIOUR",
    "OTHER",
  ],
  priority: ["LOW", "MEDIUM", "HIGH", "URGENT"],
  department: [
    "MAINTENANCE",
    "HOUSEKEEPING",
    "MESS",
    "SECURITY",
    "IT",
    "ADMINISTRATION",
    "WARDEN_OFFICE",
  ],
  complaintStatus: ["SUBMITTED", "TRIAGED", "IN_PROGRESS", "RESOLVED", "CLOSED", "REJECTED"],
  leaveType: ["HOME_VISIT", "MEDICAL", "ACADEMIC", "EMERGENCY", "OTHER"],
  leaveStatus: ["PENDING", "APPROVED", "REJECTED", "COMPLETED", "CANCELLED"],
  mealType: ["BREAKFAST", "LUNCH", "SNACKS", "DINNER"],
  roomType: ["SINGLE", "DOUBLE", "TRIPLE", "DORMITORY"],
  roomStatus: ["AVAILABLE", "FULL", "MAINTENANCE", "CLOSED"],
  bedStatus: ["VACANT", "RESERVED", "OUT_OF_SERVICE"],
  studentStatus: ["ACTIVE", "PROSPECTIVE", "ON_LEAVE", "ALUMNI", "SUSPENDED"],
  invoiceStatus: ["ISSUED", "PARTIALLY_PAID", "OVERDUE", "PAID", "VOID"],
  paymentMethod: ["CASH", "ESEWA", "KHALTI", "BANK_TRANSFER", "CHEQUE"],
  documentType: [
    "HOSTEL_RULES",
    "FEE_POLICY",
    "LEAVE_POLICY",
    "MESS_POLICY",
    "NOTICE",
    "FAQ",
    "OTHER",
  ],
  audience: ["ALL", "STUDENTS", "STAFF"],
} as const;

export const OPEN_COMPLAINT_STATUSES = ["SUBMITTED", "TRIAGED", "IN_PROGRESS"];

export function audienceLabel(value: string): string {
  return value === "ALL" ? "Everyone" : value === "STUDENTS" ? "Residents" : "Staff";
}

/** Older ledger lines named a payment by its internal id; show those plainly. */
export function ledgerDescription(description: string): string {
  return /^Payment [0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(description) ? "Payment received" : description;
}
