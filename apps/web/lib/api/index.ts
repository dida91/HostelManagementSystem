/**
 * Typed wrappers for every FastAPI operation the UI uses, grouped by domain.
 * Paths are relative to /api/v1 (the BFF adds the prefix).
 */
import { download, qs, request } from "./client";
import type * as T from "./types";

export { ApiError, onSessionExpired } from "./client";
export type * from "./types";

type Paging = { limit?: number; offset?: number };

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ access_token: string }>("/auth/login", {
        method: "POST",
        json: { email, password },
      }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    me: () => request<T.Me>("/auth/me"),
    changePassword: (current_password: string, new_password: string) =>
      request<unknown>("/auth/change-password", {
        method: "POST",
        json: { current_password, new_password },
      }),
  },

  students: {
    list: (p: Paging & { status?: string; q?: string } = {}) =>
      request<T.Page<T.Student>>(`/students${qs(p)}`),
    get: (id: string) => request<T.Student>(`/students/${id}`),
    create: (body: T.StudentCreate) =>
      request<T.Student>("/students", { method: "POST", json: body }),
    update: (id: string, body: T.StudentUpdate) =>
      request<T.Student>(`/students/${id}`, { method: "PATCH", json: body }),
    deactivate: (id: string, body: T.StudentDeactivate) =>
      request<T.Deactivation>(`/students/${id}/deactivate`, { method: "POST", json: body }),
    reactivate: (id: string) =>
      request<T.Student>(`/students/${id}/reactivate`, { method: "POST" }),
    resetPassword: (id: string, new_password: string) =>
      request<void>(`/students/${id}/reset-password`, {
        method: "POST",
        json: { new_password },
      }),
  },

  rooms: {
    blocks: () => request<T.Block[]>("/rooms/blocks"),
    createBlock: (body: T.BlockCreate) =>
      request<T.Block>("/rooms/blocks", { method: "POST", json: body }),
    updateBlock: (id: string, body: T.BlockUpdate) =>
      request<T.Block>(`/rooms/blocks/${id}`, { method: "PATCH", json: body }),
    deleteBlock: (id: string) => request<void>(`/rooms/blocks/${id}`, { method: "DELETE" }),
    list: (p: { block_id?: string; status?: string } = {}) =>
      request<T.Room[]>(`/rooms${qs(p)}`),
    get: (id: string) => request<T.RoomDetail>(`/rooms/${id}`),
    create: (body: T.RoomCreate) => request<T.RoomDetail>("/rooms", { method: "POST", json: body }),
    update: (id: string, body: T.RoomUpdate) =>
      request<T.RoomDetail>(`/rooms/${id}`, { method: "PATCH", json: body }),
    remove: (id: string) => request<void>(`/rooms/${id}`, { method: "DELETE" }),
    setBed: (bedId: string, status: string) =>
      request<T.Bed>(`/rooms/beds/${bedId}`, { method: "PATCH", json: { status } }),
    allocate: (body: { student_id: string; bed_id: string; from_date: string }) =>
      request<T.Assignment>("/rooms/allocations", { method: "POST", json: body }),
    vacate: (assignmentId: string) =>
      request<T.Assignment>(`/rooms/allocations/${assignmentId}/vacate`, { method: "POST" }),
  },

  complaints: {
    list: (p: Paging & { status?: string[] } = {}) =>
      request<T.Page<T.Complaint>>(`/complaints${qs(p)}`),
    get: (id: string) => request<T.ComplaintDetail>(`/complaints/${id}`),
    create: (text: string) =>
      request<T.Complaint>("/complaints", { method: "POST", json: { text } }),
    override: (id: string, body: T.ComplaintOverride) =>
      request<T.Complaint>(`/complaints/${id}`, { method: "PATCH", json: body }),
  },

  leave: {
    list: (p: Paging & { status?: string } = {}) =>
      request<T.Page<T.Leave>>(`/leave${qs(p)}`),
    create: (body: T.LeaveCreate) => request<T.Leave>("/leave", { method: "POST", json: body }),
    decide: (id: string, body: T.LeaveDecision) =>
      request<T.Leave>(`/leave/${id}`, { method: "PATCH", json: body }),
  },

  fees: {
    balance: (studentId?: string) =>
      request<T.Balance>(`/fees/balance${qs({ student_id: studentId })}`),
    ledger: (studentId?: string) =>
      request<T.LedgerEntry[]>(`/fees/ledger${qs({ student_id: studentId })}`),
    invoices: (
      p: Paging & { student_id?: string; status?: string; billing_period?: string } = {},
    ) => request<T.Page<T.Invoice>>(`/fees/invoices${qs(p)}`),
    invoice: (id: string) => request<T.InvoiceDetail>(`/fees/invoices/${id}`),
    createInvoice: (body: T.InvoiceCreate) =>
      request<T.Invoice>("/fees/invoices", { method: "POST", json: body }),
    generate: (period?: string, due_day?: number) =>
      request<T.InvoiceGeneration>("/fees/invoices/generate", {
        method: "POST",
        json: { period, due_day },
      }),
    /** The key must stay the same when the same submission is retried. */
    recordPayment: (body: T.PaymentCreate, idempotencyKey: string) =>
      request<T.Payment>("/fees/payments", {
        method: "POST",
        json: body,
        headers: { "Idempotency-Key": idempotencyKey },
      }),
    structures: () => request<T.FeeStructure[]>("/fees/structures"),
    createStructure: (body: T.FeeStructureCreate) =>
      request<T.FeeStructure>("/fees/structures", { method: "POST", json: body }),
    updateStructure: (id: string, body: T.FeeStructureUpdate) =>
      request<T.FeeStructure>(`/fees/structures/${id}`, { method: "PATCH", json: body }),
    deleteStructure: (id: string) =>
      request<void>(`/fees/structures/${id}`, { method: "DELETE" }),
  },

  mess: {
    menu: () => request<T.MenuItem[]>("/mess/menu"),
    setMenu: (day: number, meal: string, items: string, serving_time: string | null) =>
      request<T.MenuItem>(`/mess/menu/${day}/${meal}`, {
        method: "PUT",
        json: { items, serving_time },
      }),
    removeMenu: (day: number, meal: string) =>
      request<void>(`/mess/menu/${day}/${meal}`, { method: "DELETE" }),
    feedback: (p: Paging = {}) => request<T.Page<T.MessFeedback>>(`/mess/feedback${qs(p)}`),
    submitFeedback: (body: T.MessFeedbackCreate) =>
      request<T.MessFeedback>("/mess/feedback", { method: "POST", json: body }),
  },

  notices: {
    list: (includeExpired = false) =>
      request<T.Notice[]>(`/announcements${qs({ include_expired: includeExpired || undefined })}`),
    create: (body: T.NoticeCreate) =>
      request<T.Notice>("/announcements", { method: "POST", json: body }),
    update: (id: string, body: T.NoticeUpdate) =>
      request<T.Notice>(`/announcements/${id}`, { method: "PATCH", json: body }),
    remove: (id: string) => request<void>(`/announcements/${id}`, { method: "DELETE" }),
  },

  notifications: {
    list: (p: Paging & { unread_only?: boolean } = {}) =>
      request<T.NotificationPage>(`/notifications${qs(p)}`),
    read: (id: string) =>
      request<T.Notification>(`/notifications/${id}/read`, { method: "POST" }),
    readAll: () => request<{ updated: number }>("/notifications/read-all", { method: "POST" }),
    deliveries: (p: Paging & { status?: string } = {}) =>
      request<T.Page<T.Delivery>>(`/notifications/deliveries${qs(p)}`),
    retryFailed: () =>
      request<{ requeued: number }>("/notifications/deliveries/retry-failed", {
        method: "POST",
      }),
  },

  documents: {
    list: (p: Paging = {}) => request<T.Page<T.HostelDocument>>(`/documents${qs(p)}`),
    upload: (form: FormData) =>
      request<T.HostelDocument>("/documents", { method: "POST", body: form }),
    reindex: (id: string) => request<unknown>(`/documents/${id}/reindex`, { method: "POST" }),
    remove: (id: string) => request<void>(`/documents/${id}`, { method: "DELETE" }),
  },

  assistant: {
    ask: (message: string) =>
      request<T.AssistantReply>("/assistant/ask", { method: "POST", json: { message } }),
    askDocuments: (question: string) =>
      request<T.RagReply>("/assistant/documents/ask", { method: "POST", json: { question } }),
  },

  analytics: {
    overview: (days = 30) => request<T.AnalyticsOverview>(`/analytics/overview${qs({ days })}`),
    insights: (days = 30) =>
      request<T.Insight>("/analytics/insights", { method: "POST", json: { days } }),
  },

  reports: {
    download: (
      kind: "students" | "occupancy" | "fees" | "complaints" | "leave",
      format: "xlsx" | "pdf",
      filters: Record<string, string | undefined> = {},
    ) => download(`/reports/${kind}${qs({ format, ...filters })}`, `${kind}.${format}`),
  },
};
