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
