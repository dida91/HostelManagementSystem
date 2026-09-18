/**
 * Browser-side API client.
 *
 * Every call goes to the Next BFF (`/api/bff/*`), never directly to FastAPI.
 * The session lives in an httpOnly cookie the browser cannot read, so no token
 * is ever held in JS, and the Gemini key is never anywhere near the client.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/bff${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    credentials: "include",
  });

  if (!res.ok) {
    let code = "error";
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      code = body.title ?? code;
      detail = body.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, detail);
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<Me>("/auth/me"),
  listComplaints: () => request<Page<Complaint>>("/complaints"),
  getComplaint: (id: string) => request<ComplaintDetail>(`/complaints/${id}`),
  createComplaint: (text: string) =>
    request<Complaint>("/complaints", { method: "POST", body: JSON.stringify({ text }) }),
  overrideComplaint: (id: string, changes: Partial<ComplaintOverride>) =>
    request<Complaint>(`/complaints/${id}`, { method: "PATCH", body: JSON.stringify(changes) }),
  ask: (message: string) =>
    request<AssistantReply>("/assistant/ask", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),
  // --- fees ---
  balance: (studentId?: string) =>
    request<Balance>(`/fees/balance${studentId ? `?student_id=${studentId}` : ""}`),
  ledger: (studentId?: string) =>
    request<LedgerEntry[]>(`/fees/ledger${studentId ? `?student_id=${studentId}` : ""}`),
  invoices: () => request<Page<Invoice>>("/fees/invoices"),

  // --- leave ---
  listLeave: () => request<Page<Leave>>("/leave"),
  createLeave: (body: LeaveCreate) =>
    request<Leave>("/leave", { method: "POST", body: JSON.stringify(body) }),
  decideLeave: (id: string, status: string, note?: string) =>
    request<Leave>(`/leave/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ status, decision_note: note }),
    }),

  // --- mess ---
  menu: () => request<MenuItem[]>("/mess/menu"),
  listFeedback: () => request<Page<MessFeedback>>("/mess/feedback"),
  submitFeedback: (body: MessFeedbackCreate) =>
    request<MessFeedback>("/mess/feedback", { method: "POST", body: JSON.stringify(body) }),

  // --- admin ---
  students: () => request<Page<Student>>("/students"),
  rooms: () => request<Room[]>("/rooms"),
  documents: () => request<Page<HostelDocument>>("/documents"),
  reindexDocument: (id: string) =>
    request<unknown>(`/documents/${id}/reindex`, { method: "POST" }),
  analyticsOverview: () => request<AnalyticsOverview>("/analytics/overview"),
  insights: (days = 30) =>
    request<{ narrative: string; metrics: AnalyticsOverview; disclaimer: string }>(
      "/analytics/insights",
      { method: "POST", body: JSON.stringify({ days }) },
    ),

  askDocuments: (question: string) =>
    request<RagReply>("/assistant/documents/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    }),
};

export interface Me {
  id: string;
  email: string;
  full_name: string;
  role: "STUDENT" | "STAFF" | "WARDEN" | "SUPER_ADMIN";
  student_id: string | null;
  student_code: string | null;
}
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface Complaint {
  id: string;
  raw_text: string;
  status: string;
  category: string | null;
  priority: string | null;
  department: string | null;
  location: string | null;
  summary: string | null;
  overridden_fields: string[] | null;
  created_at: string;
  resolved_at: string | null;
}
export interface ComplaintAI {
  status: string;
  category: string | null;
  priority: string | null;
  sentiment: string | null;
  location: string | null;
  summary: string | null;
  suggested_department: string | null;
  confidence: number | null;
  model: string;
  prompt_version: string;
}
export interface ComplaintDetail extends Complaint {
  ai_analysis: ComplaintAI | null;
}
export interface ComplaintOverride {
  category: string;
  priority: string;
  department: string;
  status: string;
  note: string;
}
export interface AssistantReply {
  text: string;
  tool_calls: { name: string; ok: boolean }[];
  citations: unknown[];
  iterations: number;
}
export interface RagReply {
  answer: string;
  grounded: boolean;
  citations: { document_title: string; page_number: number | null; section_path: string | null }[];
}

export interface Balance {
  currency: string;
  total_charged: string;
  total_paid: string;
  outstanding: string;
  as_of: string;
}
export interface LedgerEntry {
  id: string;
  entry_type: "DEBIT" | "CREDIT";
  amount_npr: string;
  description: string;
  occurred_at: string;
}
export interface Invoice {
  id: string;
  invoice_number: string;
  period_start: string;
  period_end: string;
  due_date: string;
  status: string;
}
export interface LeaveCreate {
  leave_type: string;
  from_date: string;
  to_date: string;
  reason: string;
  destination?: string;
  guardian_consent: boolean;
}
export interface Leave {
  id: string;
  leave_type: string;
  from_date: string;
  to_date: string;
  reason: string;
  status: string;
  decision_note: string | null;
  created_at: string;
}
export interface MenuItem {
  day_of_week: number;
  meal_type: string;
  items: string;
  serving_time: string | null;
}
export interface MessFeedbackCreate {
  meal_date: string;
  meal_type: string;
  rating: number;
  comment?: string;
}
export interface MessFeedback {
  id: string;
  meal_date: string;
  meal_type: string;
  rating: number;
  comment: string | null;
  created_at: string;
  analysis: {
    sentiment: string | null;
    topics: string[] | null;
    issues: string[] | null;
    summary: string | null;
  } | null;
}
export interface Student {
  id: string;
  student_code: string;
  full_name: string;
  email: string;
  college: string | null;
  program: string | null;
  status: string;
}
export interface Room {
  id: string;
  floor: number;
  room_number: string;
  capacity: number;
  room_type: string;
  status: string;
  occupied: number;
}
export interface HostelDocument {
  id: string;
  title: string;
  filename: string;
  doc_type: string;
  status: string;
  page_count: number | null;
  chunk_count: number;
  created_at: string;
}
export interface AnalyticsOverview {
  generated_at: string;
  occupancy: {
    total_beds: number;
    occupied_beds: number;
    vacant_beds: number;
    occupancy_rate_percent: number;
  };
  complaints: {
    total: number;
    change_percent: number | null;
    open: number;
    by_category: Record<string, number>;
    median_resolution_hours: number | null;
  };
  fees: {
    currency: string;
    total_charged: string;
    total_collected: string;
    total_outstanding: string;
    collection_rate_percent: number;
  };
  mess: { responses: number; average_rating: number | null };
}
