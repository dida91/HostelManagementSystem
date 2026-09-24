/**
 * Browser-side transport for the BFF.
 *
 * Every call goes to the Next.js BFF (`/api/bff/*`), never directly to FastAPI.
 * The session lives in httpOnly cookies the browser cannot read, so no token is
 * ever held in JavaScript.
 *
 * Sessions: the access cookie lives 15 minutes. On a 401 the client renews the
 * session once with the refresh cookie and retries. Renewal is single-flight
 * (one request for any number of concurrent 401s) and serialised across tabs
 * with the Web Locks API: the backend treats a reused refresh token as theft and
 * revokes every session, so two tabs must never refresh with the same token.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    /** Field-level validation messages keyed by field name (from 422 bodies). */
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

const BFF = "/api/bff";
const REFRESHED_AT = "kutumba:session-refreshed-at";

type Listener = () => void;
const expiredListeners = new Set<Listener>();

/** Called when the session can no longer be renewed (signed out elsewhere, expired). */
export function onSessionExpired(listener: Listener): () => void {
  expiredListeners.add(listener);
  return () => expiredListeners.delete(listener);
}

function readStamp(): number {
  try {
    return Number(window.localStorage.getItem(REFRESHED_AT) ?? 0);
  } catch {
    return 0;
  }
}

function writeStamp(): void {
  try {
    window.localStorage.setItem(REFRESHED_AT, String(Date.now()));
  } catch {
    /* storage unavailable: the lock alone still serialises this tab */
  }
}

let inflight: Promise<boolean> | null = null;

async function refreshOnce(): Promise<boolean> {
  // Another tab may have renewed while this one waited for the lock; its new
  // cookies are already shared, so just retry.
  if (Date.now() - readStamp() < 15_000) return true;
  // No JSON content type: the endpoint reads the refresh cookie.
  const res = await fetch(`${BFF}/auth/refresh`, { method: "POST", credentials: "include" });
  if (res.ok) writeStamp();
  return res.ok;
}

function startRenewal(): Promise<boolean> {
  const locks = typeof navigator !== "undefined" ? navigator.locks : undefined;
  const attempt = locks
    ? (locks.request("kutumba-session-renewal", refreshOnce) as unknown as Promise<boolean>)
    : refreshOnce();
  return attempt
    .catch(() => false)
    .finally(() => {
      inflight = null;
    });
}

function renewSession(): Promise<boolean> {
  inflight ??= startRenewal();
  return inflight;
}

export interface RequestOptions extends Omit<RequestInit, "body"> {
  json?: unknown;
  body?: BodyInit | null;
}

/** Low-level fetch through the BFF with one transparent session renewal. */
export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const attempt = () => {
    const headers = new Headers(options.headers);
    let body = options.body;
    if (options.json !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(options.json);
    }
    return fetch(`${BFF}${path}`, { ...options, headers, body, credentials: "include" });
  };

  const res = await attempt();
  if (res.status !== 401 || path.startsWith("/auth/login") || path.startsWith("/auth/refresh")) {
    return res;
  }
  if (await renewSession()) {
    const retried = await attempt();
    if (retried.status !== 401) return retried;
  }
  expiredListeners.forEach((listener) => listener());
  return res;
}

const DEFAULT_MESSAGES: Record<number, string> = {
  401: "Your session has ended. Sign in again to continue.",
  403: "Your account doesn't have access to this.",
  404: "That item no longer exists.",
  409: "That conflicts with the current state. Refresh and try again.",
  422: "Some details need attention.",
  429: "Too many requests. Wait a minute and try again.",
  503: "The service is temporarily unavailable. Try again shortly.",
};

export async function toApiError(res: Response): Promise<ApiError> {
  let code = "error";
  let detail = DEFAULT_MESSAGES[res.status] ?? `Something went wrong (${res.status}).`;
  const fields: Record<string, string> = {};
  try {
    const body = await res.json();
    code = body.title ?? code;
    detail = body.detail ?? detail;
    for (const f of body.errors?.fields ?? []) {
      const key = (f.loc as (string | number)[])
        .filter((part) => part !== "body" && part !== "query" && part !== "path")
        .join(".");
      if (key && !fields[key]) fields[key] = String(f.msg).replace(/^Value error, /, "");
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(res.status, code, detail, fields);
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let res: Response;
  try {
    res = await apiFetch(path, options);
  } catch {
    throw new ApiError(0, "network", "Can't reach the hostel server. Check your connection.");
  }
  if (!res.ok) throw await toApiError(res);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

/** Download a file (reports) through the BFF, with the same session handling. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw await toApiError(res);
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const name = /filename="?([^";]+)"?/i.exec(disposition)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

type QueryValue = string | number | boolean | null | undefined | (string | number)[];

/** Build a query string; arrays repeat the key, empty values are dropped. */
export function qs(params: Record<string, QueryValue>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, String(v)));
    else search.set(key, String(value));
  }
  const out = search.toString();
  return out ? `?${out}` : "";
}
