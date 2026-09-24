# AI-Powered Smart Hostel Management and Data Analytics System

Partner: **Kutumba 1 Girls Hostel, Pokhara**
Duration: 17 September 2026 – 31 December 2026

A web application that puts a hostel's daily running in one place: residents report
problems, ask for leave, see their fees and ask questions; the warden and staff register
residents, allocate beds, handle complaints, approve leave, bill and record payments,
publish notices and see how the hostel is doing. AI suggests, summarises and answers from
the hostel's own documents; people decide.

**Documentation: [`docs/`](docs/README.md).** Start with
[why it exists](docs/01-project-overview.md), [what it can do](docs/02-features.md) and
[how to run it](docs/03-getting-started.md); there is a [user guide](docs/04-user-guide.md)
with screenshots, a [technical reference](docs/05-technical-reference.md) and an
[API reference](docs/06-api-reference.md).

Technically: a modular monolith, Next.js frontend → FastAPI backend → PostgreSQL/pgvector,
with Google Gemini behind a provider abstraction.

```
Next.js (BFF route handlers)  ─ httpOnly cookies, never holds an API key
        ▼
FastAPI  api/ · services/ · repositories/ · ai/ · workers/
        ▼
PostgreSQL 16 + pgvector          Redis (broker, cache)
        ▲
        └── Celery workers (AI analysis, ingestion, embeddings)
```

## Quick start

```bash
# 1. Infrastructure (pgvector on 5434, redis on 6380)
docker compose -f infrastructure/docker-compose.yml up -d

# 2. Backend
cd apps/api
cp .env.example .env          # then set SECRET_KEY and GEMINI_API_KEY (or AI_REQUIRED=false)
uv venv && uv pip install -e ".[dev]"
./.venv/bin/alembic upgrade head
./.venv/bin/python scripts_seed.py
./.venv/bin/uvicorn app.main:app --reload

# 3. Worker + scheduler (separate shell)
./.venv/bin/celery -A app.workers.celery_app.celery_app worker -B -l info

# 4. Frontend
cd apps/web
cp .env.example .env.local
npm install && npm run dev
```

Open http://localhost:3000. Seeded accounts (development only):

| Role | Email | Password |
|---|---|---|
| Warden | `warden@kutumba.local` | `WardenPass123!` |
| Student | `sita@kutumba.local` | `StudentPass123!` |
| Student | `mina@kutumba.local` | `StudentPass123!` |

The seed creates no staff account; see
[Adding a staff or warden account](docs/03-getting-started.md#adding-a-staff-or-warden-account).

## The Gemini key

`GEMINI_API_KEY` is read **only** by the FastAPI process.

- It is never sent to the browser and is never a `NEXT_PUBLIC_*` variable.
- `.env` is gitignored; `.env.example` holds placeholders only.
- Logs redact it; API errors never include provider messages.
- With `AI_REQUIRED=true` and no key, the app **refuses to start** with an
  actionable message. There is no stub or fake implementation to mask it.
- With `AI_REQUIRED=false` the system runs fully with AI features returning 503:
  students can still file complaints and staff can still triage them.

## Verification

```bash
cd apps/api
./.venv/bin/python -m pytest tests/ -q     # tests
./.venv/bin/ruff check app tests           # lint + provider-import boundary
./.venv/bin/mypy app                       # types
./.venv/bin/alembic check                  # model/migration drift
cd ../web
npm run lint && npm run typecheck && npm run build
```

## Evaluation

```bash
cd apps/api
./.venv/bin/python ../../ai/evaluation/runners/eval_complaints.py
```

Requires a real key. Reports land in `ai/evaluation/reports/`. No accuracy is
claimed anywhere in this repo without a report to back it.

## API surface

74 operations under `/api/v1` (interactive docs at http://localhost:8000/docs):

| Group | Endpoints |
|---|---|
| auth | login, refresh, logout, me, change password |
| students | list/search, create, get, edit, deactivate (alumni/suspended), reactivate, reset password |
| rooms | blocks CRUD, rooms CRUD (beds created with the room), room detail with occupants, bed status, allocate, vacate |
| complaints | create, list, get, staff override |
| leave | request, list, approve/reject |
| fees | balance, ledger, fee structures CRUD, invoices (list, detail, create), monthly generation, payments |
| mess | menu (read, set, remove), submit feedback, list feedback |
| announcements | list (by audience), create, edit, delete |
| notifications | inbox, mark read, mark all read, delivery log, retry failed deliveries |
| reports | residents, occupancy, fees, complaints, leave -- each as Excel or PDF |
| documents | upload, list, reindex, delete |
| assistant | ask (tool-calling), ask documents (RAG) |
| analytics | overview, occupancy, complaints, fees, AI insights |
| health | live, ready |

## Background workers and schedule

```bash
make worker   # worker + scheduler (-B) for local development
make beat     # production: run exactly one scheduler next to the workers
```

On-demand tasks: `ai.analyse_complaint`, `ai.analyse_mess_feedback`,
`ai.ingest_document`, `notifications.dispatch`. They are queued only after the
request's transaction commits.

| Job | When (hostel time) |
|---|---|
| Send queued email/SMS (retries with backoff) | every 30 s |
| Notify announcements whose publish time arrived | every 5 min |
| Generate monthly invoices (room rent + monthly fees) | 1st of the month, 06:00 |
| Mark unpaid invoices past due as OVERDUE | daily 00:30 |
| Fee due reminders (`FEE_REMINDER_DAYS_BEFORE_DUE`) | daily 09:00 |
| Complete approved leave that has ended | daily 00:45 |
| Purge expired refresh tokens | daily 03:15 |

Every job is idempotent, so a retry or an accidental second scheduler is harmless.

## Notifications

In-app notifications always work. Email and SMS are off until configured in
`apps/api/.env` (see `.env.example`): set `SMTP_HOST` for email, and
`SMS_PROVIDER=sparrow` with `SPARROW_SMS_TOKEN`/`SPARROW_SMS_FROM` for SMS.
There is no fake sender. SMS goes only to valid Nepali mobile numbers, and only
for leave decisions, fee reminders and overdue notices. The warden can see every
delivery, and retry failed ones, at `/api/v1/notifications/deliveries`.

The Sparrow SMS adapter follows the provider's documented v2 API but has not
been run against a live account; verify it with a real token before relying on it.

## Frontend

Next.js App Router in `apps/web`, styled with the "Phewa Dusk" design system
([`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md)): lake-dark surfaces, marigold for the
one action that matters, Anek Latin/Devanagari so Nepali text sits naturally
beside English.

| Who | Pages |
|---|---|
| Resident | Home, Complaints, Leave, Fees, Mess, Notices, Notifications, Assistant, Account |
| Office (staff, warden, administrator) | Home, Analytics, Students, Rooms, Leave, Complaints, Mess, Notices, Fees, Reports, Assistant, Documents, Notifications, Account |

- **Data.** The browser only talks to `/api/bff/*`, which forwards to FastAPI
  with the httpOnly session cookies. Types come from the API's OpenAPI schema:
  with the API running on :8000, `npm run gen:api` regenerates
  `lib/api/schema.d.ts`. Server state lives in TanStack Query hooks
  (`lib/queries`); pages never call `fetch` directly.
- **Permissions.** `lib/permissions.ts` mirrors the backend's role gates so the
  UI only offers what the API will allow; the API remains the authority.
- **3D.** Two scenes, both presentation only: the Machhapuchhre horizon (sign-in
  and the home banner) and the block model on Rooms, coloured by occupancy.
  three.js loads lazily on those pages only, pauses when off screen or in a
  background tab, holds still under reduced motion (the OS setting or Account ›
  Reduce motion), and falls back to an SVG drawing or the room grid without WebGL.
- **Phones.** Every page works at 390 px: tables drop secondary columns (the
  detail drawer shows everything), the sidebar becomes a menu sheet, and the 3D
  model is view-only on touch so the page still scrolls.

## Tests

Integration tests run against a separate `hostel_test` database, rebuilt from
migrations and the seed at the start of every run, so they never touch
development data. Tests never publish to the real Celery broker.

## Documentation

Everything is indexed in [`docs/README.md`](docs/README.md):

- [`docs/01-project-overview.md`](docs/01-project-overview.md) — why the project exists, who it helps, what it does not do
- [`docs/02-features.md`](docs/02-features.md) — every function, by role and module
- [`docs/03-getting-started.md`](docs/03-getting-started.md) — install, run, configure, test, go live, troubleshoot
- [`docs/04-user-guide.md`](docs/04-user-guide.md) — task-by-task guide with screenshots
- [`docs/05-technical-reference.md`](docs/05-technical-reference.md) — architecture, data, security, AI, known limitations
- [`docs/06-api-reference.md`](docs/06-api-reference.md) — every endpoint

Design and history:

- [`PROJECT_ARCHITECTURE.md`](PROJECT_ARCHITECTURE.md) — detailed backend and data description (its frontend sections describe the code before the rebuild)
- [`FRONTEND_AUDIT.md`](FRONTEND_AUDIT.md) — what the old frontend did and lacked, and the backend-to-frontend gap analysis
- [`DESIGN_SYSTEM.md`](DESIGN_SYSTEM.md) — tokens, type, components, motion, 3D and chart rules
- [`docs/adr/`](docs/adr/) — architecture decision records
