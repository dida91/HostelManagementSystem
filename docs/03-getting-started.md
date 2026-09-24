# Getting started: install, run and configure

This page takes you from an empty machine to a running system with sample data, then
covers configuration, tests, going live and fixing common problems.

> **Tested on** Ubuntu Linux. The commands are for a Linux or macOS shell (`bash`). On
> Windows use WSL 2 with an Ubuntu image. macOS should work the same way but was not
> tested.

Contents: [What runs where](#1-what-runs-where) · [What you need](#2-what-you-need) ·
[Set-up, step by step](#3-set-up-step-by-step) · [Sample accounts](#4-sample-accounts-and-data) ·
[Running without a Gemini key](#5-running-without-a-gemini-key) ·
[Configuration reference](#6-configuration-reference) · [Optional extras](#7-optional-extras) ·
[Adding a staff or warden account](#adding-a-staff-or-warden-account) ·
[Tests and checks](#8-tests-and-checks) · [Backups and resets](#9-backups-and-resets) ·
[Before going live](#10-before-going-live) · [Troubleshooting](#11-troubleshooting)

---

## 1. What runs where

```
   Browser ──► Web app (Next.js)  :3000 ──► API (FastAPI) :8000 ──► PostgreSQL + pgvector :5434
                  │  serves the pages and proxies          │                  ▲
                  │  /api/bff/* to the API                 └──► Redis :6380 ──┤
                                                                    ▲         │
                                                    Worker + scheduler (Celery)
                                                    email, AI analysis, indexing, monthly jobs
```

| Part | What it is | Port | Needed for |
|---|---|---|---|
| **PostgreSQL** (with the pgvector extension) | The database, including the document search index | 5434 | Everything |
| **Redis** | Queue for background work, rate limits | 6380 | Background jobs, rate limiting |
| **API** | FastAPI application. Interactive docs at `/docs` | 8000 | Everything |
| **Worker** | Celery worker with the scheduler built in (`-B`) | none | Email, AI analysis, document indexing, scheduled jobs |
| **Web app** | Next.js. The only thing the browser talks to | 3000 | The interface |

The database and Redis run in Docker. The API, worker and web app run directly on your machine.
The host ports 5434 and 6380 are deliberately unusual so they do not clash with a PostgreSQL
or Redis you may already have.

**Without the worker** the interface still works for everything that happens inside a request
(records, allocations, payments, in-app notifications). What stops: email, AI suggestions on
complaints and meal feedback, indexing of uploaded documents (they stay "Processing"), and the
scheduled jobs (monthly invoices, overdue marking, reminders, scheduled notices).

---

## 2. What you need

| Tool | Version | Why | Check |
|---|---|---|---|
| Docker with Compose v2 | recent | Runs PostgreSQL and Redis | `docker compose version` |
| Python | 3.12 | The API and worker | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | any recent | Creates the Python environment and installs packages (installed with `pip install uv` or `pipx install uv`) | `uv --version` |
| Node.js and npm | 22 | The web app | `node --version` |
| A Gemini API key | optional | Turns the AI features on. Free at [Google AI Studio](https://aistudio.google.com/) | see [section 5](#5-running-without-a-gemini-key) |
| A Devanagari font | optional | Nepali text in PDF reports. On Ubuntu or Debian: `sudo apt install fonts-noto-core` | `ls /usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf` |

Why `uv`: the plain `python3 -m venv` route needs an extra system package on Ubuntu and Debian
(`sudo apt install python3.12-venv`) and fails without it. If you prefer it, install that package,
run `python3.12 -m venv .venv`, and use `./.venv/bin/pip install -e ".[dev]"` in place of the `uv`
commands below.

---

## 3. Set-up, step by step

Run these from the project folder (the one that contains `apps/`, `docs/` and `Makefile`). Each step
ends with a way to check it worked. `make` shortcuts are in [the table below](#make-shortcuts).

### Step 1. Start the database and Redis

```bash
docker compose -f infrastructure/docker-compose.yml up -d
docker compose -f infrastructure/docker-compose.yml ps
```

Both `hostel_db` and `hostel_redis` should show `healthy` after a few seconds. The database
user, password and name are all `hostel`, which is fine on your own machine and must be changed for
anything else (see [Before going live](#10-before-going-live)).

### Step 2. Configure the API

```bash
cd apps/api
cp .env.example .env
```

Open `apps/api/.env` and set two things:

- `SECRET_KEY`: any long random string. One way to make it:
  `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `GEMINI_API_KEY`: your key. **No key?** Set `AI_REQUIRED=false` instead. Without either, the API
  refuses to start and tells you why (see [section 5](#5-running-without-a-gemini-key)).

Everything else in the file already has a working local default. The API reads `.env` from the
folder it is started in, so always start it from `apps/api` (the `make` shortcuts do this for you).
`.env` is ignored by git and must never be committed.

### Step 3. Install the API's packages

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
```

This creates `apps/api/.venv` and installs the API with its development tools.

### Step 4. Create the tables and the sample data

```bash
./.venv/bin/alembic upgrade head
./.venv/bin/python scripts_seed.py
```

You should see four `Running upgrade` lines (`0001_extensions` to `0004_notifications_billing`)
and then `seeded: 3 users, 2 students, 6 rooms, 12 beds, ledger, menu, announcement`.
Running the seed a second time prints `already seeded; skipping` and changes nothing.

### Step 5. Start the API

```bash
./.venv/bin/uvicorn app.main:app --reload
```

Check it in a browser or with `curl`:

- <http://localhost:8000/api/v1/health/ready> should show
  `{"database":"ok","redis":"ok","ai_configured":true,"status":"ok"}` (`ai_configured` is `false`
  without a key, which is fine when `AI_REQUIRED=false`).
- <http://localhost:8000/docs> is the interactive API documentation.

Leave this terminal running.

### Step 6. Start the worker and scheduler

Open a **second terminal**:

```bash
cd apps/api
./.venv/bin/celery -A app.workers.celery_app.celery_app worker -B -l info
```

You should see the list of ten tasks, then `celery@... ready.`, then a line every 30 seconds
like `Scheduler: Sending due task notifications-dispatch`. Leave it running.

### Step 7. Start the web app

Open a **third terminal**:

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

`.env.local` holds a single setting, `API_INTERNAL_URL=http://localhost:8000`, which already points
at the API you started. The first page load compiles the app and takes a few seconds.

### Step 8. Open it and sign in

Go to <http://localhost:3000>. You are sent to the sign-in page. Use one of the
[sample accounts](#4-sample-accounts-and-data): for example `warden@kutumba.local` with
`WardenPass123!`.

### Make shortcuts

| Command | Does |
|---|---|
| `make up` / `make down` | Start or stop PostgreSQL and Redis |
| `make migrate` | `alembic upgrade head` |
| `make seed` | Load the sample data |
| `make api` | Start the API with auto-reload |
| `make worker` | Start the worker with the scheduler (local use) |
| `make beat` | Start only the scheduler (for production, once, next to the workers) |
| `make web` | Start the web app in development mode |
| `make test` | Run the backend tests |
| `make lint`, `make types` | Style and type checks |
| `make check` | Everything CI runs: lint, types, migration drift check, tests, web type check |
| `make eval` | Run the AI evaluation sets (needs a real key; see [section 8](#8-tests-and-checks)) |

---

## 4. Sample accounts and data

Development only. These accounts are made by the seed script. **Never use them, or these
passwords, on a real system.**

| Role | Email | Password |
|---|---|---|
| Warden | `warden@kutumba.local` | `WardenPass123!` |
| Resident | `sita@kutumba.local` | `StudentPass123!` |
| Resident | `mina@kutumba.local` | `StudentPass123!` |

The seed creates one warden and two residents (Sita, room 101 bed A, with 8,000 NPR outstanding;
Mina, room 102 bed A); one block ("A Block", 3 floors) with 6 double rooms and 12 beds at 8,000 NPR
a month; breakfast and dinner for every day of the week; and one notice. There is **no staff
account** and **no fee schedule**: see [Adding a staff or warden account](#adding-a-staff-or-warden-account).

A five-minute tour that touches everything:

1. Sign in as the **warden**. Open **Students** and register a resident (the button
   next to the password field generates one).
2. Open **Rooms**, select a room with a free bed and allocate the new resident.
3. Open **Fees > Fee schedule** and add a monthly fee (for example "Mess", NPR 4,500). Then
   **Bill a month** to invoice everyone, and record a payment against one invoice.
4. Sign out and sign in as the new resident (or **Sita**). Look at **Fees**, file a complaint under
   **Complaints**, and request leave under **Leave**.
5. Sign back in as the warden. The complaint is on **Complaints** (with an AI suggestion
   if you configured a key and the worker is running) and the leave request is on **Leave**. Approve it.
6. As the resident again, open the bell: it now holds notifications about the room, the invoice, the
   payment and the leave decision.

The [user guide](04-user-guide.md) walks through each of these with screenshots.

---

## 5. Running without a Gemini key

Set `AI_REQUIRED=false` in `apps/api/.env` and leave `GEMINI_API_KEY` empty. The system runs fully;
only the AI features switch off, and they say so instead of failing:

| Feature | Without a key |
|---|---|
| Records, allocations, fees, payments, leave, notices, reports, analytics figures | Work normally |
| A new complaint | Is saved. It gets no AI suggestion; staff sort it by hand |
| Meal feedback | Is saved without the AI mood and issues |
| Assistant, document questions, AI briefing | Show "unavailable" (the API answers `503`) |
| Uploaded documents | Cannot be indexed, so the assistant cannot use them |

With the default `AI_REQUIRED=true` and no key, the API stops at start-up with:

```
GEMINI_API_KEY is not set, but AI_REQUIRED=true.
  Fix: add GEMINI_API_KEY to apps/api/.env (copy apps/api/.env.example).
  Or:  set AI_REQUIRED=false to boot with AI endpoints disabled.
```

That is deliberate: there is no fake AI that would make an unconfigured system look healthy.

**Getting a key.** Create one at [Google AI Studio](https://aistudio.google.com/) and paste it into
`apps/api/.env` as `GEMINI_API_KEY=...`. It stays on the server: the browser never sees it, and the
web app has no setting for it. Restart the API and the worker after changing `.env`.

**Free-tier limits.** A free key allows only a small number of AI requests per day per model (about 20
when checked in September 2026), and returns errors ("rate limited") once they are used up. That is
enough to try every feature a few times, not to run the hostel. The two text models are deliberately
different (`GEMINI_TEXT_MODEL` for the assistant, `GEMINI_FAST_MODEL` for triage and summaries) so the
quota is spread across both. Embeddings, which index documents, are free.

**What is sent to Google.** With AI on: complaint text, meal comments, assistant questions and the
resident's own record values the assistant looks up, uploaded document text, and summary statistics.
Read Google's current terms for your tier before using real resident data.

---

## 6. Configuration reference

### API (`apps/api/.env`)

All of these are optional except as noted; the defaults suit a local machine.

| Variable | Default | What it does |
|---|---|---|
| `APP_ENV` | `local` | `local`, `test`, `staging` or `production`. Production turns on the safety checks in [section 10](#10-before-going-live) |
| `APP_DEBUG` | `false` | Must be `false` in production |
| `SECRET_KEY` | `dev-only-change-me` | Signs the sign-in tokens. **Set a long random value.** Refused in production if left at the default |
| `CORS_ORIGINS` | `http://localhost:3000` | Browser origins allowed to call the API directly. The web app itself does not need this, as it goes through its own proxy |
| `WEB_BASE_URL` | `http://localhost:3000` | The address residents use; put in the links inside emails |
| `API_BASE_URL` | `http://localhost:8000` | Reserved. Not used by the application today |
| `DATABASE_URL` | `postgresql+asyncpg://hostel:hostel@localhost:5434/hostel` | Database connection for the API |
| `DATABASE_URL_SYNC` | `postgresql+psycopg://hostel:hostel@localhost:5434/hostel` | The same database, used by migrations |
| `REDIS_URL` | `redis://localhost:6380/0` | Rate limits and the AI circuit breaker |
| `CELERY_BROKER_URL` | `redis://localhost:6380/1` | Queue for background work |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6380/2` | Task results |
| `ACCESS_TOKEN_TTL_MINUTES` | `15` | How long a sign-in token lasts before it is renewed |
| `REFRESH_TOKEN_TTL_DAYS` | `7` | How long a session can be renewed without signing in again |
| `STORAGE_DIR` | `./storage` | Where uploaded documents are kept (back this up) |
| `MAX_UPLOAD_BYTES` | `20971520` (20 MB) | Largest document upload |
| `HOSTEL_TIMEZONE` | `Asia/Kathmandu` | "Today", due dates and scheduled jobs use this, not the server's clock |
| `AUTO_GENERATE_MONTHLY_INVOICES` | `true` | Create invoices on the 1st. `false` leaves billing to the warden |
| `INVOICE_DUE_DAY` | `10` | Day of the month invoices fall due (1 to 28) |
| `FEE_REMINDER_DAYS_BEFORE_DUE` | `3` | How many days before the due date the reminder goes out |
| `REPORT_DEVANAGARI_FONT` | `/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf` | Font file used for Nepali text in PDFs. Change it on macOS or Windows |
| `GEMINI_API_KEY` | *(none)* | The AI key. Required unless `AI_REQUIRED=false` |
| `AI_REQUIRED` | `true` | `true`: refuse to start without a key. `false`: run with AI switched off |
| `GEMINI_TEXT_MODEL` | `gemini-3.5-flash` | Model for the assistant and document answers |
| `GEMINI_FAST_MODEL` | `gemini-3.5-flash-lite` | Model for complaint triage, meal feedback and the briefing |
| `GEMINI_EMBEDDING_MODEL` | `gemini-embedding-001` | Model that indexes documents for search |
| `GEMINI_EMBEDDING_DIM` | `768` | Size of each embedding. The database column is created for 768, so leave this alone unless you also change the schema with a new migration and re-index every document |
| `GEMINI_EMBEDDING_FREE_TIER` | `true` | Report embedding cost as zero. Set `false` on a paid key |
| `GEMINI_TIMEOUT_SECONDS` | `30` | How long to wait for one AI call |
| `GEMINI_MAX_RETRIES` | `3` | Retries per AI call (0 to 5) |
| `GEMINI_MAX_TOOL_ITERATIONS` | `5` | Most tool calls the assistant may chain for one question |
| `AI_LOG_PAYLOADS` | `false` | Log full prompts and answers. For local debugging only; never in production |
| `SMTP_HOST` | *(empty)* | Empty turns email off. Set it to turn email on |
| `SMTP_PORT` | `587` | Mail server port |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | *(empty)* | Mail server login, if it needs one |
| `SMTP_SECURITY` | `starttls` | `starttls`, `ssl` or `none`. `none` is refused in production |
| `SMTP_TIMEOUT_SECONDS` | `15` | How long to wait for the mail server |
| `EMAIL_FROM` | `Kutumba Hostel <no-reply@kutumba.local>` | The sender shown on emails |
| `SMS_PROVIDER` | `none` | `none` or `sparrow`. **Leave as `none`**: SMS is not enabled in this project |
| `SPARROW_SMS_TOKEN`, `SPARROW_SMS_FROM`, `SPARROW_SMS_URL` | *(empty)*, *(empty)*, Sparrow's v2 address | Only read when `SMS_PROVIDER=sparrow` |

### Web app (`apps/web/.env.local`)

| Variable | Default | What it does |
|---|---|---|
| `API_INTERNAL_URL` | `http://localhost:8000` | Where the web app's server reaches the API. Read by the server only; the browser never sees it |

The web app has no other settings and holds no secret. Sessions are cookies issued by the API.

---

## 7. Optional extras

### Email

Off until `SMTP_HOST` is set. To try it without a real mail server, run a mail catcher such as
[Mailpit](https://github.com/axllent/mailpit) and put this in `apps/api/.env`, then restart the API and
worker:

```
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_SECURITY=none
```

Every notification now also arrives as an email at the person's account address, visible in Mailpit at
<http://localhost:8025>. Failed sends are retried and visible to the warden under
**Notifications > Email and SMS log**.

### Nepali text in PDF reports

Install a Devanagari font (`sudo apt install fonts-noto-core` on Ubuntu or Debian) or point
`REPORT_DEVANAGARI_FONT` at any Devanagari `.ttf`. Without the font, PDFs print a note saying the font is
missing; the Excel export always has the exact text.

### SMS

Not enabled, and not used in this project. The Sparrow adapter exists but has never run against a live
account. Leave `SMS_PROVIDER=none`.

---

## Adding a staff or warden account

Residents are registered in the app (**Students > Register a student**). Accounts with the **Staff**
or **Warden** role have no screen yet, and the seed creates only one warden. Until a screen exists, add
one with this command. It asks for the password (so it never appears on screen or in your shell history),
and uses the application's own password hashing.

Run it from `apps/api`, with the database running and `.env` in place. Change the email and name, and pick
`UserRole.STAFF` or `UserRole.WARDEN`:

```bash
read -rs -p "Password (10+ characters): " NEW_USER_PASSWORD; echo
export NEW_USER_PASSWORD
./.venv/bin/python - <<'EOF'
import asyncio
import os

from app.core.db import AsyncSessionLocal
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User


async def main() -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            User(
                email="office.staff@example.com".lower(),
                full_name="Office Staff",
                password_hash=hash_password(os.environ["NEW_USER_PASSWORD"]),
                role=UserRole.STAFF,  # or UserRole.WARDEN
            )
        )
        await session.commit()
    print("created")


asyncio.run(main())
EOF
unset NEW_USER_PASSWORD
```

The person can sign in straight away and should change the password on the **Account** page. A staff
account sees everything in [the staff column](02-features.md#who-can-do-what).

---

## 8. Tests and checks

```bash
make test        # 132 backend tests (about 40 seconds)
make lint types  # style and type checks
make check       # all of the above plus the migration drift check and the web type check
cd apps/web && npm run lint && npm run typecheck && npm run build
```

- The tests need the Docker database running and the `apps/api/.venv` from step 3. They build their own
  database, `hostel_test`, from the migrations and seed at the start of every run, so **they never touch
  your development data**. They never talk to the real queue or to Gemini.
- CI (`.github/workflows/ci.yml`) runs the API checks against a fresh database, the web type check and
  build, and a scan for committed secrets. It does not yet run the web lint.
- **AI evaluation** (`make eval`) runs the real Gemini pipeline over labelled example sets: 12 complaints
  and 6 rule questions in [`ai/evaluation/datasets/`](../ai/evaluation/datasets/). It needs a real key,
  spends quota, and writes its results to `ai/evaluation/reports/` (ignored by git). **No results exist
  yet**, so this project claims no AI accuracy.

---

## 9. Backups and resets

**What to back up.** The PostgreSQL database and the `apps/api/storage/` folder (uploaded documents). For
example:

```bash
docker exec hostel_db pg_dump -U hostel hostel > hostel-backup.sql
```

**Starting again from a clean database (destroys all data in it).** Stop the API and worker, then:

```bash
docker compose -f infrastructure/docker-compose.yml down -v   # -v deletes the stored data
docker compose -f infrastructure/docker-compose.yml up -d
cd apps/api && ./.venv/bin/alembic upgrade head && ./.venv/bin/python scripts_seed.py
```

---

## 10. Before going live

Everything here was built and tried on a development machine. **It has not been deployed or piloted with
real residents.** This checklist comes from the application's own safety checks and is a starting point,
not a tested deployment recipe.

**Configuration**
- [ ] `APP_ENV=production`, `APP_DEBUG=false`, `AI_LOG_PAYLOADS=false`. In production the API refuses to
      start with the default `SECRET_KEY`, with `APP_DEBUG` on, with `AI_LOG_PAYLOADS=true` (when AI is
      required), or with email sent without encryption (`SMTP_SECURITY=none`).
- [ ] A long random `SECRET_KEY`, kept secret and stable (changing it signs everyone out).
- [ ] `WEB_BASE_URL` and `CORS_ORIGINS` set to the real address.
- [ ] A Gemini key on a **paid** plan if AI is to be used daily, and a decision, made with the hostel, about
      sending resident data to Google.
- [ ] Email configured (`SMTP_*`), and `EMAIL_FROM` set to an address you control.

**Hosting**
- [ ] **HTTPS in front of the web app.** In production the session cookies are marked `Secure`, so a browser
      will not send them over plain HTTP and sign-in will appear to work but not stick.
- [ ] Only the web app is reachable from outside. Keep the API, PostgreSQL and Redis on a private network.
- [ ] Change the database password from `hostel` (in `infrastructure/docker-compose.yml` and both database
      URLs) and do not publish the database and Redis ports.
- [ ] If the web app and the API run on different machines, tell the API to trust the web app's forwarded
      client addresses (uvicorn's `--forwarded-allow-ips`), or every resident shares one sign-in rate limit.
- [ ] Build the web app once (`npm run build`) and run it with `npm run start`, not `npm run dev`.
- [ ] Run `alembic upgrade head` on every deployment, before starting the new API.
- [ ] Run the worker permanently, and **exactly one scheduler** (`make beat`) next to the workers, or run a single
      `worker -B`. Two schedulers would double-send scheduled jobs (they are safe to repeat, but wasteful).
- [ ] Install a Devanagari font on the server for Nepali PDFs.

**Operations**
- [ ] Backups of the database and `STORAGE_DIR`, and a tested restore.
- [ ] Create the real warden and staff accounts (see above), then **delete or disable the sample accounts**.
- [ ] Register residents with individual, strong first passwords, and ask them to change them.

---

## 11. Troubleshooting

| What you see | Likely cause and fix |
|---|---|
| The API stops at start-up with `GEMINI_API_KEY is not set, but AI_REQUIRED=true` | Add a key to `apps/api/.env`, or set `AI_REQUIRED=false` |
| `connection refused` on port 5434 when migrating or starting the API | The database is not running. `docker compose -f infrastructure/docker-compose.yml up -d`, then check with `ps` |
| `alembic` or `uvicorn` "command not found" | Use the full path `./.venv/bin/alembic` from `apps/api`, or run the `make` shortcuts. The virtual environment was not created (step 3) |
| `relation ... does not exist` | The tables were not created. Run `./.venv/bin/alembic upgrade head` |
| Port already in use (3000, 8000, 5434, 6380) | Something else uses it. Stop it, or start the process on another port and update `API_INTERNAL_URL` and `CORS_ORIGINS` |
| Sign-in says the password is wrong for a sample account | The seed did not run, or you ran it against a different database. Run the seed (step 4) |
| `429 Too many requests` when signing in | More than 10 attempts in a minute. Wait a minute |
| Every page shows an error and the network tab shows `503` from `/api/bff/...` | The web app cannot reach the API. Check that the API is running and that `API_INTERNAL_URL` in `apps/web/.env.local` is right. Restart `npm run dev` after editing it |
| The assistant or AI briefing says "unavailable" | No key (`AI_REQUIRED=false`), a wrong key, or the free-tier quota is used up for today. `GET /api/v1/health/ready` shows `ai_configured` |
| Complaints never get an AI suggestion; uploaded documents stay "Processing" | The worker is not running (step 6), or the key/quota problem above |
| Emails never arrive | `SMTP_HOST` is empty, or the worker is not running. Look at **Notifications > Email and SMS log** as the warden |
| A PDF report shows a note about a missing font instead of Nepali text | Install the Devanagari font or set `REPORT_DEVANAGARI_FONT` ([section 7](#7-optional-extras)) |
| `python3 -m venv` fails on Ubuntu | Use `uv` as in step 3, or `sudo apt install python3.12-venv` |
| The web app will not install or build | It was built and tested with Node 22. Check `node --version` |
| Tests fail immediately with a database error | The Docker database is not running, or `apps/api/.venv` is missing (the tests call `.venv/bin/alembic`) |
