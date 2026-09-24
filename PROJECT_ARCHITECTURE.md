# Project Architecture — Kutumba Hostel Management System

> **Phase 1 deliverable.** Describes the repository as it stands on **24 September 2026**,
> including the backend additions made in the current working session, not committed yet
> (notifications, monthly billing, rooms/students administration, reports, scheduled jobs).
> Everything here was read from the code. Statements that come from reading code, without
> reproducing the behaviour, are marked *(by inspection)*.
>
> **Superseded for the frontend.** This file describes the codebase *before* the frontend was
> rebuilt. The backend sections (3 to 6, 15 and the backend parts of 10 and 13) are still accurate.
> Out of date: the frontend rows of §1, and §2, §7, §8 (frontend column), §9, §11, §12, §14 and
> the frontend items of §10 and §13, all of which the rebuild resolved. For the current system
> see [`docs/`](docs/README.md), especially the
> [technical reference](docs/05-technical-reference.md), plus `DESIGN_SYSTEM.md` and
> `FRONTEND_AUDIT.md` § Outcome.

---

## 1. Technology stack

| Layer | Technology | Version (installed) |
|---|---|---|
| Frontend framework | Next.js (App Router), React | 15.5.26, 19.0.0 *(15.1.6 when this was written)* |
| Frontend language | TypeScript (`strict`) | 5.9.3 |
| Server state | TanStack Query | 5.103.1 |
| Client state | zustand (toasts and preferences; *was unused when this was written*) | 5.0.15 |
| Styling | Tailwind CSS + PostCSS/autoprefixer | 3.4.19 |
| UI components | Hand-written shared components (`components/ui/`), lucide-react icons, three.js with @react-three/fiber for two 3D scenes; no component library. *(Was a single `components/ui.tsx` with none of these when this was written.)* | — |
| Backend framework | FastAPI on uvicorn | 0.141.1, 0.53.0 |
| Validation / settings | Pydantic v2, pydantic-settings | 2.13.5, 2.15.0 |
| ORM / migrations | SQLAlchemy 2.0 (async via asyncpg, sync via psycopg 3), Alembic | 2.0.54, 1.20.0 |
| Database | PostgreSQL 16 + `pgvector` + `pg_trgm` (Docker `pgvector/pgvector:pg16`, host port 5434) | 16 |
| Cache / broker | Redis 7 (Docker, host port 6380): rate limits, circuit breaker, Celery broker/results | 7 |
| Background jobs | Celery (prefork) + Celery beat | 5.6.3 |
| AI | Google Gemini via `google-genai` (text: `gemini-3.5-flash`, fast: `gemini-3.5-flash-lite`, embeddings: `gemini-embedding-001` @ 768 dims) | 2.24.0 |
| Auth / crypto | argon2-cffi (passwords), PyJWT (HS256) | 25.1.0, 2.14.0 |
| Documents | pypdf, python-magic | 6.19.0 |
| Reports | openpyxl (Excel), reportlab + uharfbuzz (PDF with shaped Devanagari) | 3.1.5, 5.0.1, 0.56.2 |
| Outbound messaging | smtplib (SMTP), httpx (Sparrow SMS) | — |
| Logging | structlog (JSON, secret redaction) | 26.1.0 |
| Quality | pytest + pytest-asyncio, ruff (lint + format, provider-import ban), mypy (`disallow_untyped_defs`) | 9.1.1, 0.16.8, 2.3.1 |
| CI | GitHub Actions: API (lint, format, types, migration round-trip, drift check, tests), web (`tsc`, `next build`), gitleaks | — |
| Runtime | Python 3.12, Node 22 | — |

Monorepo layout:

```
apps/api/        FastAPI app (app/), Alembic migrations, tests, seed script
apps/web/        Next.js app (app/, components/, lib/)
ai/evaluation/   Offline evaluation datasets + runners (complaint triage, RAG)
infrastructure/  docker-compose (Postgres+pgvector, Redis)
docs/            Documentation (overview, features, getting started, user guide, technical and API reference)
docs/adr/        Architecture decision records 0001–0003
```

---

## 2. Frontend architecture

```
Browser ── fetch("/api/bff/<path>", credentials: include) ──► Next.js route handler
                                                              app/api/bff/[...path]/route.ts
                                                                   │ forwards method, headers,
                                                                   │ body, cookies; relays Set-Cookie
                                                                   ▼
                                                             FastAPI /api/v1/<path>
```

- **Rendering model.** Every page is a client component (`"use client"`). The only
  server component is `app/page.tsx`, which redirects `/` → `/login`. Data is fetched
  in the browser with TanStack Query.
- **BFF (backend-for-frontend).** `app/api/bff/[...path]/route.ts` proxies every call
  to FastAPI (`API_INTERNAL_URL`). Session tokens live only in httpOnly cookies. The
  browser never sees a token, and FastAPI is never called directly from the browser.
- **API client.** `lib/api.ts` has a single `request<T>()` helper that always sends JSON
  and throws `ApiError(status, code, detail)` from RFC 7807 bodies. It also holds typed
  wrappers for 23 calls and hand-maintained TypeScript interfaces that mirror backend
  schemas.
- **Auth guard.** `components/shell.tsx` runs the `["me"]` query and redirects to
  `/login` when it errors. There is no `middleware.ts`, so nothing is protected
  server-side, and pages briefly render "Loading…" before redirecting.
- **Layout.** `Shell` = `Nav` (a top bar of text links, chosen by role) + `<main
  class="max-w-6xl">`. There is no sidebar, no page-header component, no breadcrumbs.
- **State.** Server state lives in TanStack Query (`retry: 1`, `staleTime: 30s`, no refetch
  on focus). Forms use local `useState`. zustand is unused.
- **Styling.** Tailwind with one custom colour ramp (`brand` green: 50/100/500/600/700/900)
  and the default slate greys. The system font stack (no `next/font`), no dark mode, no
  design tokens beyond that colour. Input class strings are copy-pasted across pages.
- **Animation / 3D.** None. The only motion is Tailwind `transition` on links and buttons.

---

## 3. Backend architecture

Layers, in `apps/api/app/`:

| Layer | Contents |
|---|---|
| `api/v1/` | 14 routers, **74 operations**. Thin: parse input, apply role gates, call services, shape output. |
| `api/deps.py` | `get_current_user` (Bearer header **or** `access_token` cookie; reloads the user and checks `is_active` on every request), `require_roles`, `Principal` for AI tools, `rate_limit(bucket)`, AI provider injection. |
| `services/` | Business logic: `auth`, `students`, `rooms`, `complaints`, `finance`, `leave`, `announcements`, `notifications`, `delivery`, `documents`, `analytics`, `reports`, `audit`. |
| `models/` | SQLAlchemy 2.0 typed models; native PostgreSQL enums (`models/enums.py`). |
| `schemas/` | Pydantic request/response models. |
| `repositories/` | **Empty package** — services use SQLAlchemy directly. |
| `ai/` | `providers/` (interfaces + Gemini, the *only* module allowed to import the SDK — enforced by ruff `banned-api`), `services/` (tool-calling chat, RAG, hybrid retrieval, ingestion, chunking, embeddings, complaint classification, feedback sentiment, analytics narration), `tools/` (role-filtered registry + 11 tools), `prompts/`, `schemas/` (structured output), `telemetry/` (one `ai_operations` row per model call, cost estimate). |
| `integrations/` | Outbound adapters: SMTP email, Sparrow SMS. |
| `reports/` | Format-neutral `Report` model → Excel / PDF renderers (no DB access). |
| `workers/` | Celery app + beat schedule, `runtime.py` (one event loop per worker process), `enqueue.py` (send tasks by name, after commit), tasks for AI, documents, notifications, scheduled jobs. |
| `core/` | `config` (env-driven settings, fail-fast validation), `db` (async + sync engines, per-request transaction, after-commit hooks), `security` (argon2, JWT), `errors` (problem+json; internals never leak), `logging` (structlog + redaction + request/user context), `ratelimit` (Redis fixed window, fails open; shared AI circuit breaker), `clock` (hostel timezone, Asia/Kathmandu). |

Cross-cutting behaviour:

- **Transactions:** one per request (`get_session`), committed after the handler returns.
  Background tasks are sent *after* commit, so a worker can never look for a row that
  isn't committed yet.
- **Errors:** every error is `application/problem+json`. SQL/provider details are logged,
  never returned.
- **AI degradation:** `AI_REQUIRED=false` boots without a key. AI endpoints return 503;
  everything else keeps working. Complaint and feedback analysis runs in the worker, so a
  failing model never blocks a submission.
- **Workers:** tasks are idempotent. Scheduled jobs (hostel time): outbox sweep every
  30 s, due announcements every 5 min, monthly invoices on the 1st at 06:00, overdue
  marking 00:30, fee reminders 09:00, leave completion 00:45, refresh-token purge 03:15.

---

## 4. Database / data architecture

31 tables (plus `alembic_version`), UUID primary keys, `timestamptz` timestamps, native enums.

| Domain | Tables | Notes |
|---|---|---|
| Identity | `users`, `refresh_tokens`, `students`, `audit_logs` | Roles SUPER_ADMIN / WARDEN / STAFF / STUDENT. Refresh tokens stored **hashed**, rotated, with reuse detection. Audit log is append-only. |
| Hostel | `blocks`, `rooms`, `beds`, `bed_assignments` | Partial unique indexes: one ACTIVE occupant per bed, one ACTIVE bed per student. Assignments are never deleted (residency history). |
| Finance | `fee_structures`, `fee_invoices`, `invoice_line_items`, `payments`, `student_ledger_entries` + sequence `invoice_number_seq` | **No balance column** — balance = SUM(DEBIT) − SUM(CREDIT) over the append-only ledger (ADR 0003). Payments idempotent via unique `idempotency_key`. One monthly invoice per student per `billing_period` (partial unique index). |
| Complaints | `complaints`, `complaint_ai_analyses`, `complaint_events` | Student text immutable; AI proposals kept separate from staff-owned effective fields; overrides recorded in `overridden_fields` + audit log. |
| Leave | `leave_requests`, `leave_documents` | `leave_documents` (attachments) **has no API**. |
| Mess & notices | `mess_menus`, `mess_feedback`, `mess_feedback_ai`, `announcements` | One feedback per student per meal. Announcements have `audience` (ALL/STUDENTS/STAFF) and `notified_at`. |
| Documents / RAG | `documents`, `document_chunks` (generated `tsvector`, trigram index), `chunk_embeddings` (`vector(768)`, HNSW cosine) | Embeddings in Postgres, not a separate vector DB (ADR 0001). |
| AI observability | `ai_operations`, `rag_queries`, `assistant_conversations`, `assistant_messages` | The two `assistant_*` tables are **never written**. |
| Notifications | `notifications`, `notification_deliveries` | In-app inbox + email/SMS outbox (claimed with `SKIP LOCKED`, retried with backoff). `dedupe_key` makes scheduled notices exactly-once per user. |

Migrations: `0001_extensions` → `0002_initial_schema` → `0003_vector_index` (hand-written
HNSW/trigram indexes) → `0004_notifications_billing` (new, uncommitted). CI checks upgrade →
downgrade → upgrade and `alembic check` (no drift). Seed (`scripts_seed.py`): 1 warden,
2 students, 1 block, 6 rooms, 12 beds, a ledger, a partial menu (breakfast + dinner),
1 announcement. **No STAFF or SUPER_ADMIN user is seeded.**

---

## 5. API architecture

REST under `/api/v1`, JSON (plus multipart upload and file downloads). Pagination is
`limit`/`offset` and returns `{items, total, limit, offset}` (default limit 20). Errors
are problem+json. Swagger UI is at `/docs` outside production.

Access key: **P** public · **A** any signed-in user · **S** STAFF/WARDEN/SUPER_ADMIN ·
**W** WARDEN/SUPER_ADMIN · **St** student only · **Own** a student sees only their own
rows (other students' records return 404).

| Group | Operations |
|---|---|
| health | `GET /health/live` P · `GET /health/ready` P |
| auth | `POST /auth/login` P (rate-limited) · `POST /auth/refresh` P · `POST /auth/logout` P · `GET /auth/me` A · `POST /auth/change-password` A (rate-limited) |
| students | `GET /students` S (status, `q` search, paged) · `POST /students` S · `GET /students/{id}` Own/S · `PATCH /students/{id}` S · `POST …/deactivate` W · `POST …/reactivate` W · `POST …/reset-password` W |
| rooms | `GET /rooms/blocks` S · `POST/PATCH/DELETE /rooms/blocks[/{id}]` W · `PATCH /rooms/beds/{id}` W · `GET /rooms` S (block, status) · `POST /rooms` W · `GET /rooms/{id}` S (beds + occupants) · `PATCH/DELETE /rooms/{id}` W · `POST /rooms/allocations` S · `POST /rooms/allocations/{id}/vacate` S |
| complaints | `POST /complaints` St · `GET /complaints` Own/S (paged) · `GET /complaints/{id}` Own/S · `PATCH /complaints/{id}` S (override + status) |
| leave | `POST /leave` St · `GET /leave` Own/S (status, paged) · `PATCH /leave/{id}` W (APPROVED/REJECTED + note) |
| fees | `GET /fees/balance` Own/S · `GET /fees/ledger` Own/S · `GET/POST/PATCH/DELETE /fees/structures[/{id}]` S read, W write · `GET /fees/invoices` Own/S (student, status, period, paged) · `POST /fees/invoices` S · `POST /fees/invoices/generate` W · `GET /fees/invoices/{id}` Own/S · `POST /fees/payments` S (**`Idempotency-Key` header required**) |
| mess | `GET /mess/menu` **P** · `PUT/DELETE /mess/menu/{day}/{meal}` S · `POST /mess/feedback` St · `GET /mess/feedback` Own/S |
| announcements | `GET /announcements` A (audience-filtered) · `POST` W · `PATCH/DELETE /{id}` W |
| notifications | `GET /notifications` A (own; unread count) · `POST /notifications/{id}/read` A · `POST /notifications/read-all` A · `GET /notifications/deliveries` W · `POST /notifications/deliveries/retry-failed` W |
| reports | `GET /reports/{students,fees}` W · `GET /reports/{occupancy,complaints,leave}` S — `?format=xlsx|pdf`, every export audited |
| documents | `POST` (multipart) · `GET` · `POST /{id}/reindex` · `DELETE /{id}` — all W |
| assistant | `POST /assistant/ask` A · `POST /assistant/documents/ask` A — both rate-limited (`ai`) |
| analytics | `GET /analytics/{overview,occupancy,complaints,fees}` S · `POST /analytics/insights` S (rate-limited `ai`) |

API contract changes made in this session (all additive unless noted):
`RoomOut`, `StudentOut`, `InvoiceOut`, `PaymentOut`, `AnnouncementOut` gained fields.
**Behaviour changes:** `GET /announcements` now requires sign-in and hides staff-only and
not-yet-published notices from students. `PATCH /leave/{id}` accepts only
APPROVED/REJECTED. A duplicate student returns 409 (was 500). Allocation checks room
status and student status. A zero-total invoice returns 422 (was 500).

---

## 6. Authentication / authorization flow

1. **Login.** Browser → `POST /api/bff/auth/login` → FastAPI verifies argon2 with uniform
   timing (unknown email ≡ wrong password) and the account's `is_active`. It issues an
   **access JWT** (HS256, 15 min, claims `sub/type/role/jti`) and a **refresh JWT** (7 days;
   SHA-256 hash stored in `refresh_tokens`). Both are set as `httpOnly`, `SameSite=Strict`
   cookies (`Secure` unless `APP_ENV=local`). The BFF relays `Set-Cookie` to the browser.
2. **Requests.** The browser sends cookies to the BFF, which forwards them. `get_current_user`
   decodes the access token, loads the user and rejects inactive accounts, so deactivation
   takes effect immediately.
3. **Authorization.**
   - Role gates: `require_roles` at router level or per endpoint.
   - Ownership: students are scoped at query level, and another student's record returns
     **404, not 403**, so its existence is not disclosed.
   - AI tools get a server-built `Principal` and have **no identity parameters**
     (ADR 0002). Tools are filtered by role before the model runs and re-checked on execute.
4. **Refresh.** `POST /auth/refresh` rotates tokens. Presenting a revoked token revokes all of
   that user's sessions. **The frontend never calls it** (see §11).
5. **Logout** revokes the refresh token and clears cookies. **Password change, warden
   reset and deactivation** revoke every session.
6. **Rate limits** (Redis; fails open if Redis is down): `auth` 10/min, `ai` 20/min,
   `default` 120/min. The identity is the user id when known, otherwise the client address
   as uvicorn sees it (see §15 on proxies).

---

## 7. Route / page map (frontend)

| Route | Intended role | In nav for | Guard | What it does |
|---|---|---|---|---|
| `/` | — | — | server redirect | → `/login` |
| `/login` | all | — | none | Email + password sign-in |
| `/dashboard` | all | students, staff | Shell | Greeting, 5 latest complaints, quick links |
| `/complaints` | student | students | Shell | File a complaint; list own complaints |
| `/leave` | student + warden | students, staff | Shell | Student: request form + own list. Staff: all requests + approve/reject |
| `/fees` | student | students | Shell | Balance cards + ledger table |
| `/mess` | all | students, staff | Shell | Today's menu, rate a meal, feedback list (staff see all) |
| `/assistant` | all | students, staff | Shell | Ask the tool-calling assistant |
| `/admin/complaints` | staff | staff ("Triage") | Shell only | Per-complaint AI suggestion + override form |
| `/admin/analytics` | staff | staff | Shell only | 4 KPI tiles, complaints-by-category bars, AI briefing |
| `/admin/documents` | **warden** | **all staff** | Shell only | Upload, list, reindex documents |
| `/api/bff/[...path]` | — | — | — | BFF proxy (route handler) |

No route checks a role in the UI. A student can open `/admin/*`, but the API refuses the
data. Pages have no 404 page, error boundary or loading route segments.

---

## 8. Feature map

| Feature | Backend | Frontend |
|---|---|---|
| Sign-in / sign-out / session | ✅ incl. refresh rotation | ⚠️ sign-in/out only; no refresh, no password change |
| Complaints (file, triage, AI analysis, overrides, audit) | ✅ | ✅ (student + staff), no filters or paging |
| Leave (request, decide, auto-complete) | ✅ | ✅ basic; no decision note, no requester name |
| Fees: balance, ledger | ✅ | ✅ student only |
| Fees: invoices, payments, fee structures, monthly billing, reminders, overdue | ✅ | ❌ |
| Rooms, blocks, beds, allocation | ✅ | ❌ |
| Student records & lifecycle | ✅ | ❌ |
| Mess menu (read) / feedback + AI sentiment | ✅ | ✅ (today's menu only) |
| Mess menu management | ✅ | ❌ |
| Announcements | ✅ | ❌ (residents cannot see notices at all) |
| Notifications (in-app, email, SMS) | ✅ | ❌ |
| Reports (Excel/PDF) | ✅ | ❌ |
| Documents / RAG ingestion | ✅ | ✅ upload/list/reindex (upload broken for PDFs *(by inspection)*); no delete |
| Document Q&A with citations (RAG) | ✅ | ❌ (client function exists, unused) |
| Assistant (tool calling) | ✅ | ✅ single-turn; citations/conversation not shown |
| Analytics + AI narration | ✅ | ✅ |
| Audit trail | ✅ written | ❌ no viewer (and no read API) |

---

## 9. Frontend → backend dependency map

| Page | API calls (via BFF) |
|---|---|
| `/login` | `POST /auth/login` |
| Shell / Nav (every page) | `GET /auth/me`, `POST /auth/logout` |
| `/dashboard` | `GET /auth/me`, `GET /complaints` |
| `/complaints` | `GET /complaints`, `POST /complaints` |
| `/leave` | `GET /auth/me`, `GET /leave`, `POST /leave`, `PATCH /leave/{id}` |
| `/fees` | `GET /fees/balance`, `GET /fees/ledger` |
| `/mess` | `GET /mess/menu`, `GET /mess/feedback`, `POST /mess/feedback` |
| `/assistant` | `POST /assistant/ask` |
| `/admin/complaints` | `GET /complaints`, then `GET /complaints/{id}` **once per listed complaint**, `PATCH /complaints/{id}` |
| `/admin/analytics` | `GET /analytics/overview`, `POST /analytics/insights` |
| `/admin/documents` | `GET /documents`, `POST /documents` (raw `fetch`, multipart), `POST /documents/{id}/reindex` |

Client wrappers defined but **used nowhere**: `api.invoices`, `api.students`, `api.rooms`,
`api.askDocuments`.

---

## 10. Backend functionality with no frontend

- **Students:** list/search, register, edit profile, deactivate (alumni/suspended),
  reactivate, reset password.
- **Rooms:** blocks, rooms, beds (status), room detail with occupants, allocate, vacate.
- **Fees (staff):** any student's balance/ledger, invoice list/detail, manual invoices,
  monthly generation, payments, fee structures.
- **Fees (student):** own invoices and invoice detail. Today students see only the ledger.
- **Mess:** set/remove menu items; the full weekly menu.
- **Announcements:** list, create, schedule, edit, delete. Residents have **no way to read notices**.
- **Notifications:** inbox, unread count, mark read; warden delivery log and retry.
- **Reports:** residents, occupancy, fees, complaints, leave — Excel/PDF.
- **Account:** change own password.
- **Documents:** delete; RAG question answering with citations (`/assistant/documents/ask`).
- **Analytics:** occupancy/complaints/fees sub-endpoints (the overview covers them, which is fine).
- **Pagination and filters** on every list endpoint. The UI always shows only the first 20
  rows: triage shows 20 of 56 complaints in the dev data.

Backend capability that is itself incomplete:

- `leave_documents` table has no API.
- Assistant write tools (`create_complaint`, `create_leave_request`) are defined but never
  offered to the model (`allow_writes=False` everywhere), and there is no confirm flow.
- `assistant_conversations` / `assistant_messages` are never written. `conversation_id` is
  only echoed back.
- `LeaveOut` has no student name or code, so a warden cannot see who asked.
- Complaint `assigned_to_user_id` and `resolution_note` are never set by any endpoint.
- Statuses with no transition: invoice `VOID`, payment `REVERSED`, leave `CANCELLED`
  (students cannot cancel), student `ON_LEAVE`.
- No API to read the audit log.

---

## 11. Frontend functionality with incomplete backend integration

1. **Sessions die after 15 minutes.** The access cookie expires and nothing calls
   `/auth/refresh` (no `refresh` string exists anywhere in `apps/web`). The 7-day refresh
   token is unused, so users are silently logged out.
2. **PDF upload is corrupted by the BFF** *(by inspection)*. `route.ts` forwards the body with
   `await req.text()`, which UTF-8-decodes binary data. Text/Markdown uploads survive; PDFs don't.
3. **Upload success is reported as failure** *(by inspection)*. `admin/documents` calls
   `e.currentTarget.reset()` *after* `await fetch(…)`, when React has already nulled
   `currentTarget`. The `TypeError` lands in the `catch` and shows "Upload failed.", and the
   list is not refreshed.
4. **Leave decisions:** no input for the decision note the API accepts. STAFF (non-warden)
   users see Approve/Reject, but the API refuses them and the mutation has no `onError`,
   so the click silently does nothing.
5. **Triage makes N+1 requests** (one `GET /complaints/{id}` per row). It is labelled "Open
   complaints" but lists every status, with no paging or filters.
6. **The dashboard is student-centric.** For staff, "Your complaints" lists all complaints,
   and the quick links point at student actions.
7. **Misused badge tones:** the ledger "Type" column renders the words *medium* / *positive*,
   and documents show *resolved* for `INDEXED`.
8. **Assistant:** `conversation_id` isn't sent back, citations aren't rendered, and the RAG
   endpoint is unused.
9. **Nav vs permissions:** "Documents" is shown to STAFF, but the API is warden-only.
10. **The query cache survives logout.** `api.logout()` doesn't clear TanStack Query, so on a
    shared device the next user can briefly see the previous user's data (up to the 30 s
    `staleTime`). This matters for a hostel office PC.
11. **Query errors are invisible.** Most `useQuery` calls ignore `isError`, so a failure
    looks like "—" or "Nothing filed yet".
12. **Type drift:** `lib/api.ts` interfaces lag the API (`Leave` lacks `student_id`; `Room`
    and `Student` lack this session's new fields).
13. **Mess dates:** the feedback form defaults `meal_date` to the UTC date, while "today's
    menu" uses the local weekday. Before 05:45 in Nepal these disagree.

---

## 12. Existing reusable components

Frontend:

| Component | File | Notes |
|---|---|---|
| `Card` (title, actions, children) | `components/ui.tsx` | Only container primitive |
| `Button` (`primary` / `ghost`) | `components/ui.tsx` | No sizes, icons or loading state |
| `Badge` (status → tone map) | `components/ui.tsx` | Tone map covers ~10 values; others fall back to grey |
| `ErrorNote` | `components/ui.tsx` | Inline alert |
| `Shell`, `Nav` | `components/` | Auth guard + role-based top nav |
| `Providers` | `app/providers.tsx` | QueryClient |
| `api`, `ApiError`, `request()` | `lib/api.ts` | Typed client |
| `clsx` | `lib/clsx.ts` | Class joiner |
| Page-local: `Select` (admin/complaints), `Stat` (admin/analytics), `TriageRow` | pages | Should be promoted to shared components |

Backend (worth reusing as-is): `require_roles` / `CurrentUser` / `PrincipalDep`, the
problem+json error types, `record_audit`, `NotificationService` + message templates,
`enqueue_after_commit`, `run_in_transaction` / `run_async`, `FinanceService`,
`RoomService`, `StudentService`, `ReportService` + renderers, `hostel_today()`.

---

## 13. Existing technical debt

**Frontend**

- No shared form or input primitives: the same ~120-character input class string is
  repeated about 15 times, validation is ad hoc, and inline errors are missing.
- No frontend tests of any kind, and no ESLint config file (`next lint` isn't runnable
  non-interactively). CI runs only `tsc` and `next build`.
- No `middleware.ts`, error boundaries, `not-found`, loading segments or security headers
  (CSP etc.) in `next.config.mjs`.
- zustand is a dependency that is never imported, and `SESSION_SECRET` in `.env.local` is
  never read.
- No i18n, although residents write in Nepali and the backend is Devanagari-aware.
- No icon system, no chart library, and no motion or 3D foundation.

**Backend**

- The `repositories/` layer is an empty placeholder.
- Dead or partial features: `assistant_conversations/messages`, the unreachable write
  tools, and `leave_documents` (see §10).
- The login rate-limit identity depends on proxy-header configuration (§15).
- No invoice void or payment reversal flow, although the statuses exist.
- `docs/architecture.md` is linked from the README but doesn't exist; this file supersedes it.
- `ai/evaluation/reports/` is empty: no accuracy figures have been produced yet.
- The Sparrow SMS adapter follows the provider's documented API but has not been run
  against a live account.
- Dev database: the test suite used to run against it and left junk (56 complaints). Fixed
  in this session: tests now use their own `hostel_test` database. The existing junk remains until
  the dev database is reset.

---

## 14. Existing UI/UX problems (summary — detailed per page in Phase 2)

- **Generic appearance:** white cards on `slate-50`, one green accent, no typography scale,
  no visual hierarchy between KPIs, content and actions.
- **Navigation:** a flat row of text links with no icons or grouping. It wraps awkwardly on
  mobile and has no `aria-current`. Staff and student information architecture aren't
  distinguished beyond the link list.
- **Data display:** lists instead of tables almost everywhere; no sorting, filtering,
  search or pagination; the fees table isn't responsive.
- **States:** plain "Loading…" text, no skeletons, silent query failures, empty states
  without calls to action.
- **Forms:** no inline validation, date ranges unconstrained in the UI, no confirmation
  for consequential actions (approve/reject, overrides).
- **Triage:** a full edit form for every complaint at once; dense, slow, hard to scan.
- **Assistant:** stacked cards rather than a conversation, no citations, no suggestions.
- **Analytics:** four tiles and one hand-drawn bar list; no trends.
- **Missing surfaces:** notices, notifications and account settings have no home in the UI.
- **Status colours:** many statuses (PENDING, APPROVED, REJECTED, IN_PROGRESS, OVERDUE,
  PAID…) render grey.
- No dark mode and no motion; accessibility is basic (labels mostly present, focus rings
  only on some inputs).

---

## 15. Potentially risky areas — do not change casually

1. **Authorization semantics.** Student scoping at query level, 404-not-403 for other
   residents' data, role gates on routers, the notification inbox scoped to its owner.
   Any UI redesign must keep calling the same endpoints and never "filter client-side"
   as a security measure.
2. **AI tool identity (ADR 0002).** Self-scoped tools must never gain a `student_id`/`user_id`
   parameter; `tests/unit/test_tool_security.py` enforces this.
3. **Financial invariants (ADR 0003).** Append-only ledger, no balance column, idempotent
   payments (`Idempotency-Key`), invoice-number sequence, one monthly invoice per student
   per period. The UI must send an idempotency key per payment attempt and must never
   compute balances itself.
4. **Occupancy invariants.** Partial unique indexes on `bed_assignments`; assignments are
   ended, never deleted; rooms/beds with history cannot be deleted.
5. **Session model.** httpOnly + SameSite=Strict cookies, tokens never in JavaScript, the
   BFF as the only path to FastAPI, and the Gemini key only in the FastAPI process. A 3D/UI
   rewrite must not introduce client-side token storage or direct browser → FastAPI calls.
6. **The BFF proxy** (`app/api/bff/[...path]/route.ts`). Every request goes through it.
   Fixing the binary-body bug belongs there, carefully, with a regression check on login
   cookies.
7. **Migrations.** Never edit an applied migration. Add a new one, keep downgrades dropping
   native enum types, and keep `alembic check` clean.
8. **Proxy/IP handling.** Behind the BFF, uvicorn trusts `X-Forwarded-For` only from
   localhost by default. If Next.js and FastAPI run on different hosts, set
   `--forwarded-allow-ips` for the BFF host; otherwise every user shares one login
   rate-limit bucket.
9. **Background job semantics.** Tasks are sent after commit, the worker keeps one event
   loop per process (prefork/solo pools only), and jobs are idempotent via dedupe keys,
   unique indexes and `SKIP LOCKED`.
10. **Error contract.** problem+json with `title`/`detail`. `lib/api.ts` depends on these
    field names.
11. **Test isolation.** `tests/conftest.py` points tests at `hostel_test` and an in-memory
    Celery broker. Removing that would again pollute dev data and spend the real Gemini quota.
