# Technical reference

How the system is built, for developers, reviewers and anyone deciding whether to trust it. For what it does
see [02-features.md](02-features.md); for every endpoint see [06-api-reference.md](06-api-reference.md). The
decisions behind the design are recorded in [`docs/adr/`](adr/), and a longer, file-by-file description of the
backend is in [`PROJECT_ARCHITECTURE.md`](../PROJECT_ARCHITECTURE.md) (its frontend sections describe the code
*before* the rebuild; see the note at its top).

Contents: [1. Architecture](#1-architecture) · [2. Technology](#2-technology) ·
[3. Repository layout](#3-repository-layout) · [4. Backend](#4-backend) · [5. Frontend](#5-frontend) ·
[6. Data model](#6-data-model) · [7. Sign-in and permissions](#7-sign-in-and-permissions) ·
[8. Background work](#8-background-work) · [9. The AI layer](#9-the-ai-layer) · [10. Security](#10-security) ·
[11. Quality and testing](#11-quality-and-testing) · [Known limitations](#known-limitations) ·
[12. Suggested next steps](#12-suggested-next-steps)

---

## 1. Architecture

A modular monolith: one FastAPI application, one Next.js application, one PostgreSQL database, one Redis, and
a Celery worker that shares the backend's code.

```
Browser
   │  HTTPS, httpOnly session cookies, never a token in JavaScript
   ▼
Next.js  (apps/web)          pages, and /api/bff/* proxy: the only thing the browser talks to
   │  server to server, forwards cookies
   ▼
FastAPI  (apps/api)          /api/v1/*   routers → services → models
   │                │
   ▼                ▼
PostgreSQL 16     Redis 7                        Google Gemini API  (optional, server side only)
+ pgvector        rate limits, queue, results          ▲
   ▲                │                                   │
   └──── Celery worker + scheduler ────────────────────┘
         email · AI analysis · document indexing · monthly jobs
```

Why it is shaped this way:

- **One deployable backend** keeps a small team's operational load low. The layers inside are separate
  enough (routers, services, AI, workers) to split later if needed.
- **The browser never talks to the API and never holds a token.** The Next.js server proxies every call and
  the session lives in `httpOnly`, `SameSite=Strict` cookies, so a script injected into a page cannot steal a
  session. The Gemini key exists only in the API process and worker.
- **PostgreSQL does the heavy lifting.** Constraints enforce the business rules that must never be broken
  (one bed per resident, one monthly invoice per resident per month); the vector index for document search lives
  in the same database, so a document and its embeddings commit together (ADR 0001); and every figure
  shown is calculated by SQL (ADR 0003).
- **Redis is optional in spirit**: rate limiting fails open, and if the queue is unreachable the request still
  succeeds and the background work is simply not started.

---

## 2. Technology

Versions installed at the time of writing (24 September 2026). `pyproject.toml` and `package-lock.json` are the
authority; the API declares minimum versions, the web app locks exact ones.

| Layer | Technology | Version |
|---|---|---|
| Web framework | Next.js (App Router), React | 15.5.26, 19.0.0 |
| Language | TypeScript (strict) | 5.9.3 |
| Server state | TanStack Query | 5.103.1 |
| Small client state (toasts, preferences) | zustand | 5.0.15 |
| Styling | Tailwind CSS with design tokens | 3.4.19 |
| Icons | lucide-react | 1.47.0 |
| 3D | three.js, @react-three/fiber | 0.186.0, 9.8.0 |
| API types | openapi-typescript (generated from the API's schema) | 7.13.0 |
| Lint | ESLint with `next/core-web-vitals` and `next/typescript` | 9.39.5 |
| API framework | FastAPI on uvicorn | 0.141.1, 0.53.0 |
| Validation and settings | Pydantic v2, pydantic-settings | 2.13.5, 2.15.0 |
| ORM and migrations | SQLAlchemy 2.0 (async with asyncpg, sync with psycopg 3), Alembic | 2.0.54, 1.20.0 |
| Database | PostgreSQL with pgvector and pg_trgm | 16.15, vector 0.8.6 |
| Queue and cache | Redis, Celery (prefork) with beat | 7.4, 5.6.3 |
| AI | Google Gemini through `google-genai`: `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-embedding-001` (768 dimensions) | 2.24.0 |
| Passwords and tokens | argon2-cffi, PyJWT (HS256) | 25.1.0, 2.14.0 |
| Documents and reports | pypdf, openpyxl, reportlab with uharfbuzz (Devanagari shaping) | 6.19.0, 3.1.5, 5.0.1 with 0.56.2 |
| Logging | structlog (JSON, secrets redacted) | 26.1.0 |
| Backend quality | pytest, pytest-asyncio, ruff (lint and format), mypy | 9.1.1, 1.4.0, 0.16.8, 2.3.1 |
| Runtime | Python, Node.js | 3.12, 22 |

---

## 3. Repository layout

```
apps/api/           the backend
  app/api/v1/         14 routers, 74 operations: thin, they parse input, check the role, call a service
  app/api/deps.py     current user, role gates, rate limits, the identity handed to AI tools
  app/services/       business rules: auth, students, rooms, complaints, finance, leave, announcements,
                      notifications, delivery, documents, analytics, reports, audit
  app/models/         SQLAlchemy models and the native enums
  app/schemas/        Pydantic request and response shapes
  app/ai/             providers/ (the only place the Gemini SDK may be imported), services/, tools/, prompts/
  app/integrations/   outbound email (SMTP) and SMS (Sparrow)
  app/reports/        format-neutral report model plus Excel and PDF renderers
  app/workers/        Celery app and schedule, task modules, enqueue-after-commit, per-process event loop
  app/core/           settings, database sessions, security, errors, logging, rate limits, clock
  alembic/versions/   four migrations
  tests/              unit/ and integration/
  scripts_seed.py     sample data
apps/web/           the frontend
  app/(auth)/         sign-in
  app/(app)/          every signed-in page, each a server page.tsx plus a client view
  app/api/bff/        the proxy route handler
  components/ui/      shared UI parts: buttons, fields, tables, dialogs, menus, toasts, states
  components/shell/   app frame: sidebar, top bar, bell, command palette, guards
  components/charts/  bar, stacked bar and meter charts with a validated palette
  components/three/   the two 3D scenes and their fallbacks
  components/domain/  parts tied to the hostel: resident picker, invoice drawer
  lib/api/            typed API client, generated schema, single-flight session renewal
  lib/queries/        TanStack Query hooks, one file per area
  lib/                permissions, labels, formatting
ai/evaluation/      labelled datasets and runners for measuring the AI (no results recorded yet)
infrastructure/     docker-compose for PostgreSQL and Redis
docs/               this documentation and the architecture decision records
```

---

## 4. Backend

**Layers.** A router validates input (Pydantic), applies the role gate, calls a service, and shapes the
output. Services hold the business rules and use SQLAlchemy directly (the `repositories/` package is an
empty placeholder). Models declare tables, constraints and enums. The AI, email and report code sit behind
their own interfaces.

**Request lifecycle.**
1. A request arrives with a Bearer token or the `access_token` cookie. `get_current_user` decodes it, loads the
   user from the database and rejects inactive accounts, so deactivation takes effect on the next request.
2. The handler runs inside **one database transaction**, committed after it returns and rolled back if it raises.
3. Work that must happen *after* the data is safely stored (queueing AI analysis, indexing, sending email) is
   registered as an **after-commit callback** and only then sent to Celery. A worker can therefore never look for
   a row that has not been committed yet, and a failed request never queues anything.
4. Errors are raised as typed exceptions and rendered as `application/problem+json`. SQL and provider details are
   logged, never returned.

**Settings** come from environment variables through one validated `Settings` object, checked at start-up: an
unsafe production configuration, or AI required without a key, stops the process with a message rather than
limping along. **Logging** is structured JSON (a readable console format when `APP_DEBUG=true`) with the request id and
user id added to every line, and API keys, tokens and passwords redacted.

**Dates and time.** "Today", due dates and every scheduled job use the hostel's timezone (`HOSTEL_TIMEZONE`,
default `Asia/Kathmandu`), not the server's; timestamps are stored as UTC.

**Money.** Amounts are `NUMERIC(12,2)` in NPR and handled as `Decimal`, never floating point.

---

## 5. Frontend

- **Rendering.** Each page is a small server component (page title and metadata) that renders a client view.
  Data is fetched in the browser with TanStack Query. A `middleware.ts` sends visitors without a session cookie to the
  sign-in page before any page code runs.
- **Talking to the API.** `lib/api/client.ts` sends every call to `/api/bff/...`. If a call returns 401 it renews the session
  once (`/auth/refresh`) and retries, with a browser lock so several open tabs renew only once. If renewal fails the
  cache is cleared and the user is sent to sign in. Types come from the API's OpenAPI schema
  (`npm run gen:api`), so once they are regenerated a backend change that breaks the frontend fails the type check.
- **Server state.** Hooks in `lib/queries/` wrap every endpoint and invalidate what a change affects. They start a refetch
  without waiting for it, so a page's own success handling (a toast, closing a dialog) is never lost when fresh data arrives.
- **Permissions in the UI.** `lib/permissions.ts` mirrors the server's role gates so buttons and pages a role cannot use are
  hidden. It is a courtesy; the server is the authority.
- **Design system.** Tokens in `tailwind.config.ts` and `globals.css`, described in [`DESIGN_SYSTEM.md`](../DESIGN_SYSTEM.md):
  a dark "lake at dusk" palette, marigold for the one primary action, restrained motion, Anek Latin and Anek Devanagari type so
  Nepali sits naturally beside English. Dialogs and drawers use the native `<dialog>` element for focus trapping and `Esc`.
- **3D.** `components/three/` holds two scenes, both presentation only: they receive data as props and report clicks through
  callbacks, and contain no API calls or business rules. They load lazily, render only while visible, pause in background tabs, stay still under reduced motion,
  and fall back to a drawing or the room grid when WebGL is missing. Charts (`components/charts/`) use a palette validated for
  colour-blind safety and contrast.
- **The proxy** (`app/api/bff/[...path]/route.ts`) forwards method, headers, raw body bytes (so PDF uploads are not corrupted) and
  cookies, and relays `Set-Cookie`. It answers `503` if the API is unreachable and sends bodiless responses (204) without a body.

---

## 6. Data model

31 tables with UUID keys, `timestamptz` timestamps and native PostgreSQL enums, built by four migrations
(`0001_extensions` to `0004_notifications_billing`). Migrations are checked in CI by applying, rolling back and
re-applying them, and by `alembic check` (no drift between models and migrations).

| Area | Tables | Rules the database enforces |
|---|---|---|
| Identity | `users`, `refresh_tokens`, `students`, `audit_logs` | Unique email and student code. Refresh tokens are stored hashed. |
| Hostel | `blocks`, `rooms`, `beds`, `bed_assignments` | At most one active occupant per bed and one active bed per resident (partial unique indexes). An end date never precedes the start. |
| Money | `fee_structures`, `fee_invoices`, `invoice_line_items`, `payments`, `student_ledger_entries`, sequence `invoice_number_seq` | No balance column: balance is the sum of the ledger. Unique payment idempotency key. One non-void monthly invoice per resident per billing period. Amounts must be positive. |
| Complaints | `complaints`, `complaint_ai_analyses`, `complaint_events` | The resident's text is never edited. The AI's proposal is stored apart from the effective fields, and `overridden_fields` lists what staff set. |
| Leave | `leave_requests`, `leave_documents` | `leave_documents` (attachments) has no API yet. |
| Mess and notices | `mess_menus`, `mess_feedback`, `mess_feedback_ai`, `announcements` | One menu entry per day and meal. One rating per resident per meal per date. |
| Documents and search | `documents`, `document_chunks`, `chunk_embeddings` | Chunks carry a generated full-text vector and a trigram index; embeddings are `vector(768)` with an HNSW cosine index. |
| AI records | `ai_operations`, `rag_queries`, `assistant_conversations`, `assistant_messages` | `ai_operations` gets one row per model call. The two `assistant_*` tables are not written yet. |
| Notifications | `notifications`, `notification_deliveries` | A `dedupe_key` makes a scheduled notice reach each person exactly once. Deliveries are claimed with `SKIP LOCKED`. |

**Balance.** `outstanding = SUM(DEBIT) - SUM(CREDIT)` over a resident's ledger, computed in SQL on every read. Invoices post a
debit and payments a credit inside the same transaction as the invoice or payment, so the ledger cannot disagree with them
(ADR 0003).

---

## 7. Sign-in and permissions

1. **Sign in.** The proxy posts the credentials to `/auth/login`. The API checks the Argon2 hash (taking the same time whether or not the
   account exists) and that the account is active, then issues an **access token** (JWT, HS256, 15 minutes) and a **refresh token**
   (JWT, 7 days, whose SHA-256 hash is stored). Both are set as `httpOnly`, `SameSite=Strict` cookies, `Secure` everywhere except
   `APP_ENV=local`.
2. **Refresh.** `/auth/refresh` rotates the pair. Presenting a token that was already used or revoked is treated as theft and ends **all** of
   that user's sessions.
3. **Sign out, password change, warden reset, deactivation** all revoke sessions.
4. **Authorization** has three layers. *Role gates* on routers and endpoints (`require_roles`). *Ownership* enforced in queries, so a
   resident cannot reach another's rows (404, or 403 for the fee-statement `student_id` parameter). And for the AI, the identity
   is built by the server from the authenticated request and injected into tools; the model is never asked who someone is (ADR 0002).
5. **Rate limits** per minute, in Redis: `auth` 10 (sign-in and password change) and `ai` 20 (the assistant and the briefing). A `default`
   bucket of 120 is defined but no ordinary endpoint uses it yet. The key is the user id when known, otherwise the client
   address as the server sees it. If Redis is down the limits fail open, so residents are never locked out.

Roles: `STUDENT` (resident), `STAFF`, `WARDEN`, `SUPER_ADMIN`. There is no API to create the last three; see
[03-getting-started.md](03-getting-started.md#adding-a-staff-or-warden-account).

---

## 8. Background work

Celery tasks run in a separate worker process. There are ten:

| Task | Trigger | Purpose |
|---|---|---|
| `ai.analyse_complaint` | A complaint is filed | AI triage; failures are stored, not raised |
| `ai.analyse_mess_feedback` | A rating with a comment | Mood, topics and issues |
| `ai.ingest_document` | Upload or re-index | Read, chunk, embed, index |
| `notifications.dispatch` | Every 30 s, and right after a request queues an email or SMS | Send queued email and SMS |
| `announcements.publish_due` | Every 5 min | Notify notices whose publish time has arrived |
| `fees.generate_monthly_invoices` | 1st, 06:00 | Bill the month |
| `fees.mark_overdue` | Daily 00:30 | Mark late invoices and notify once |
| `fees.send_due_reminders` | Daily 09:00 | Remind before the due date |
| `leave.complete_finished` | Daily 00:45 | Complete finished leave |
| `auth.purge_expired_refresh_tokens` | Daily 03:15 | Delete expired tokens |

**Notifications use an outbox.** A notification is written to the database inside the request. If email or SMS is configured, a delivery row per
channel is written in the same transaction. The dispatcher claims due rows with `SKIP LOCKED` (so several workers never send the same one), sends them,
and on failure retries after 1, 5 and then 30 minutes, up to four attempts, then marks them failed for the warden to retry. A crashed
worker's claim expires after ten minutes and the message is picked up again. So a crash cannot lose an email, but if it happens in the moment
between sending and recording the send, that email may go out twice.

**Idempotency.** Every scheduled job can run twice harmlessly, through unique indexes, dedupe keys and status checks, so a retry or an accidental second
scheduler does no damage. Run one scheduler (`make beat`, or one worker with `-B`).

**Runtime detail.** The worker keeps a single long-lived event loop per process (`workers/runtime.py`), which is why it must run with the prefork or
solo pool. Tasks are sent by name after commit (`workers/enqueue.py`).

---

## 9. The AI layer

Everything AI-related lives in `apps/api/app/ai/`, and only `providers/gemini.py` may import the Gemini SDK. That is enforced by a lint rule, so the
rest of the code depends on the interfaces `LLMProvider`, `EmbeddingProvider` and `DocumentUnderstandingProvider` and the provider can be replaced.

| Feature | How it works | Model |
|---|---|---|
| **Complaint triage** | The text goes to the model with instructions to base everything on what was written and to treat safety, security, harassment and health risks as urgent. The answer is *structured output* constrained to the allowed categories, priorities and departments, then re-validated. It is stored in `complaint_ai_analyses` and only fills fields staff have not set. | fast |
| **Meal feedback** | A comment becomes a mood, topics and issues, stored beside the untouched original. | fast |
| **Analytics briefing** | The model receives the *finished* numbers and is told to use them exactly and never add one. | fast |
| **Assistant, "Your records"** | A bounded loop (at most `GEMINI_MAX_TOOL_ITERATIONS`, default 5): the model may request tools, the server runs them as the signed-in person and returns results, until the model answers. Nine read tools exist: profile, room, fee balance, leave, complaints, menu, notices, occupancy (staff), document search. Two write tools (create complaint, create leave) are defined but never offered to the model. | text |
| **Assistant, "Rules and policies" (RAG)** | The question is embedded and searched two ways at once (pgvector cosine similarity and PostgreSQL full-text), and the rankings are merged with reciprocal-rank fusion, which needs no tuned weights. The model answers *only* from the top passages, must cite them, and must say "not grounded" when they do not contain the answer. With no passages found, the model is not called at all. | text |
| **Document indexing** | Text is extracted natively page by page; pages with too little text (scans) go to the model's document reader. Text is split along headings and clauses (English and Nepali heading patterns) with a Devanagari-aware size estimate, then embedded with `RETRIEVAL_DOCUMENT` task type (queries use `RETRIEVAL_QUERY`). | embedding |

**Safeguards**
- **Identity is never model output.** Self-scoped tools declare no identity parameter; the executor injects the caller. A unit test fails the build if one
  ever gains one. Tools are filtered by role before the model runs and checked again when executed (ADR 0002).
- **No AI-computed figures.** Balances and counts come from tools or SQL; the prompts forbid stating a number from memory and require an honest failure message
  instead of an estimate (ADR 0003).
- **Untrusted text is fenced.** Retrieved document text and resident-written text are placed in delimited blocks marked as data, not instructions.
- **Advisory only.** The model can read and explain; it cannot write to the database from the chat loop.
- **Observability.** Every model call is recorded in `ai_operations` (operation, model, prompt version, status, error category, latency, tokens, estimated
  cost, request and user id). Prompt versions are stored with each result so outputs stay attributable and evaluation runs comparable.
- **Resilience.** Timeouts, bounded retries with backoff, a shared circuit breaker that stops calling a failing model for a minute after five straight
  failures, and per-user rate limits. Provider errors reach users only as "unavailable".
- **Degradation.** With no key (`AI_REQUIRED=false`) AI endpoints return 503 and everything else works.

**What leaves the system.** Text sent to Gemini: complaint text, meal comments, assistant questions and the values returned by the tools the model calls for
that resident, uploaded document text, questions asked of the documents, and aggregate analytics numbers. Nothing is sent when AI is off. `AI_LOG_PAYLOADS`
(off by default, refused in production when AI is required) would write prompts and answers to the logs.

**Evaluation.** [`ai/evaluation/`](../ai/evaluation/) contains 12 labelled complaints and 6 rule questions with runners that measure classification precision, recall and
F1 per class, and retrieval recall, ranking, grounding and citation validity. The runners need a real key and write to `ai/evaluation/reports/`. **No run has been
recorded**, so no accuracy figure exists or is claimed.

---

## 10. Security

| Area | What is done |
|---|---|
| Passwords | Argon2id, rehashed when parameters change; at least 10 characters; equal work for unknown and known emails |
| Sessions | Short-lived access token, rotating refresh token stored hashed with reuse detection, `httpOnly` `SameSite=Strict` cookies, all sessions revoked on password change, reset and deactivation |
| Authorization | Role gates on the server for every endpoint, ownership in queries, 404 for other residents' data, AI identity injected by the server |
| Input | Pydantic validation on every request; uploads checked by content (not name or declared type), capped in size and stored under random names outside any served directory; Excel cells that could run as formulas are neutralised |
| Abuse | Redis rate limits for sign-in and AI; sign-in identical for unknown user and wrong password; idempotency keys on payments |
| Data | Personal-data reports limited to the warden and sent with `Cache-Control: no-store`; complaint reports omit the complainant; deletion of rooms and blocks with history refused; audit log of administrative changes |
| Secrets | Read only from the environment; never logged (redacted); the Gemini key is server-side only; `.env` files are git-ignored and CI scans history for committed secrets |
| Errors | RFC 7807 responses that never contain SQL, stack traces or provider messages |
| Production guards | The API will not start in production with the default secret, debug on, unencrypted email, or (when AI is required) AI payload logging on |
| Not done | See [Known limitations](#known-limitations): security headers such as a Content-Security-Policy are not set by the web app, there is no audit-log viewer, and no independent security review or penetration test has been done |

---

## 11. Quality and testing

**Backend: 132 automated tests** (`make test`, about 40 seconds).

| Group | Tests | Covers |
|---|---:|---|
| Integration | 86 | Auth and permissions, residents, rooms, complaints, leave, fees and billing, notifications, delivery and scheduled jobs, reports and menu, domain endpoints, migrations |
| Unit | 46 | Notification wording and Nepali number handling, outbound senders, report renderers, chunking, error classification, AI tool security |

The integration tests build their own database (`hostel_test`) from the migrations and seed at the start of every run and use an in-memory queue, so they never touch
development data or the real Gemini quota.

**Static checks.** `ruff` (lint, format, and the Gemini-SDK import boundary), `mypy` with untyped definitions disallowed, and `alembic check`.

**CI** (`.github/workflows/ci.yml`) runs the API checks on a fresh pgvector and Redis, the migration round trip, the web type check and build, and a secret scan.

**Frontend.** Type checking, ESLint (`npm run lint`, clean with zero warnings), and a production build. During development the interface was also checked by hand and with
scripted browser runs as both a resident and the warden, at desktop, laptop and phone widths, on an isolated database with synthetic data. **Those browser scripts are not part of
the repository or CI**, and the frontend has no automated tests, which is the largest testing gap.

**Not tested:** behaviour under load, a real deployment, a live SMS account, a real mail server, and accuracy of the AI (see above).

---

## Known limitations

Grouped by how much they matter for a real launch.

**Before real use**
- Not deployed or piloted with real residents; no load testing.
- AI accuracy unmeasured (no evaluation run recorded). The Gemini free tier allows only a few AI requests a day; a paid key and a decision about sending resident data
  to Google are needed for daily use.
- **No screen to create staff or extra warden accounts**, and `SUPER_ADMIN` behaves exactly like the warden.
- **Staff are not alerted when a complaint is filed**, urgent ones included. They see it in the list and on the home screen. Only leave requests notify the warden.
- **Mistakes cannot be reversed in the app.** Invoices can be `VOID` and payments `REVERSED` in the database, but no screen or endpoint does it. There are no credit notes,
  refunds, discounts, late fees or deposits, and mid-month arrivals are billed a full month (issue a manual invoice for a part month).
- The analytics "outstanding" tile is *charged minus collected* over everyone, so a resident who has paid ahead offsets another's arrears in that total. Each resident's own
  balance is exact.
- No security headers (for example Content-Security-Policy) from the web app; add them at the reverse proxy. No penetration test.

**Gaps in what is recorded or shown**
- The audit log and the history of complaint status changes and staff notes are stored but **no screen or API reads them**. Complaint `assigned_to_user_id` and `resolution_note`
  are never set.
- Leave attachments (`leave_documents`) have no API; leave cannot be cancelled by a resident (`CANCELLED` exists but is unused).
- Assistant conversations are not stored (`assistant_conversations` and `assistant_messages` are never written), and the assistant answers one question at a time.
- Guardians are recorded but never contacted; notifications go to the resident's own email. SMS is disabled and untested against a live account.
- The interface is English only; there is no translation layer, although Nepali text works in everything residents write.
- No data-retention, export or erasure tooling for personal data.
- The mess menu repeats weekly; there is no date-specific override.
- The notices list returns the newest 50.

**Engineering debt**
- Web lint is not yet in CI; the browser test scripts are not in the repository.
- `repositories/` is an empty package. Unused: the `API_BASE_URL` setting, the `python-magic` dependency, the `RequireAdmin` gate.
- Adding a value to a native PostgreSQL enum needs a migration.
- The development database still holds test leftovers from before the tests had their own database.
- Behind a reverse proxy on another host, uvicorn must be told to trust the proxy's forwarded addresses, or every user shares one sign-in rate limit.

---

## 12. Suggested next steps

In the order that would most reduce risk before a launch:

1. Pilot with the warden and a few residents on a real (private) deployment, using the [go-live checklist](03-getting-started.md#10-before-going-live).
2. Decide with the hostel how resident data may be sent to the AI provider; move to a paid key if the AI features stay on.
3. Add a screen to create staff and warden accounts, and a staff alert (in-app and email) for new and urgent complaints.
4. Add invoice void and payment reversal with an audit trail, and a viewer for the audit log and complaint history.
5. Run the AI evaluation sets with a real key and record the results; extend the labelled examples with the hostel's own (anonymised) wording, including Nepali.
6. Put the browser checks into the repository and CI, and add the web lint to CI.
7. Set security headers at the proxy, then commission a security review.
