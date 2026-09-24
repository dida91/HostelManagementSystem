/**
 * Friendly names for the generated OpenAPI types.
 *
 * `schema.d.ts` is generated from the running API (`npm run gen:api`) and must
 * not be edited by hand. Money arrives as decimal strings; never do arithmetic on
 * it for display beyond formatting (figures are computed by the backend).
 */
import type { components } from "./schema";

type S = components["schemas"];

export type Page<T> = { items: T[]; total: number; limit: number; offset: number };

export type Role = "STUDENT" | "STAFF" | "WARDEN" | "SUPER_ADMIN";
export type Me = Omit<S["MeOut"], "role"> & { role: Role };

export type Student = S["StudentOut"];
export type StudentCreate = S["StudentCreate"];
export type StudentUpdate = S["StudentUpdate"];
export type StudentDeactivate = S["StudentDeactivate"];
export type Deactivation = S["DeactivationOut"];

export type Block = S["BlockOut"];
export type BlockCreate = S["BlockCreate"];
export type BlockUpdate = S["BlockUpdate"];
export type Room = S["RoomOut"];
export type RoomDetail = S["RoomDetailOut"];
export type RoomCreate = S["RoomCreate"];
export type RoomUpdate = S["RoomUpdate"];
export type Bed = S["BedOut"];
export type Assignment = S["AssignmentOut"];

export type Complaint = S["ComplaintOut"];
export type ComplaintDetail = S["ComplaintDetailOut"];
export type ComplaintAI = S["ComplaintAIOut"];
export type ComplaintOverride = S["ComplaintOverride"];

export type Leave = S["LeaveOut"];
export type LeaveCreate = S["LeaveCreate"];
export type LeaveDecision = S["LeaveDecision"];

export type Balance = S["BalanceOut"];
export type LedgerEntry = S["LedgerEntryOut"];
export type Invoice = S["InvoiceOut"];
export type InvoiceDetail = S["InvoiceDetailOut"];
export type InvoiceCreate = S["InvoiceCreate"];
export type InvoiceGeneration = S["InvoiceGenerationOut"];
export type Payment = S["PaymentOut"];
export type PaymentCreate = S["PaymentCreate"];
export type FeeStructure = S["FeeStructureOut"];
export type FeeStructureCreate = S["FeeStructureCreate"];
export type FeeStructureUpdate = S["FeeStructureUpdate"];

export type MenuItem = S["MenuOut"];
export type MessFeedback = S["MessFeedbackOut"];
export type MessFeedbackCreate = S["MessFeedbackCreate"];

export type Notice = S["AnnouncementOut"];
export type NoticeCreate = S["AnnouncementCreate"];
export type NoticeUpdate = S["AnnouncementUpdate"];

export type Notification = S["NotificationOut"];
export type NotificationPage = S["NotificationPage"];
export type Delivery = S["DeliveryOut"];

export type HostelDocument = S["DocumentOut"];
export type AssistantReply = S["AssistantReply"];
export type RagReply = S["RagReply"];

// Analytics endpoints return computed dicts without a response model.
export interface AnalyticsOverview {
  generated_at: string;
  occupancy: {
    total_beds: number;
    occupied_beds: number;
    vacant_beds: number;
    occupancy_rate_percent: number;
  };
  complaints: {
    window_days: number;
    total: number;
    previous_period_total: number;
    change_percent: number | null;
    by_category: Record<string, number>;
    by_status: Record<string, number>;
    open: number;
    median_resolution_hours: number | null;
  };
  fees: {
    currency: string;
    total_charged: string;
    total_collected: string;
    total_outstanding: string;
    collection_rate_percent: number;
  };
  mess: {
    window_days: number;
    responses: number;
    average_rating: number | null;
    average_by_meal: Record<string, number>;
  };
}

export interface Insight {
  narrative: string;
  metrics: AnalyticsOverview;
  disclaimer: string;
}
