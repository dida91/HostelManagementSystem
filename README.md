# AI-Powered Smart Hostel Management and Data Analytics System

Partner: **Kutumba 1 Girls Hostel, Pokhara**
Duration: 17 September 2026 – 31 December 2026

A modular monolith: Next.js frontend → FastAPI backend → PostgreSQL/pgvector,
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
cp .env.example .env          # then add your GEMINI_API_KEY
uv venv && uv pip install -e ".[dev]"
./.venv/bin/alembic upgrade head
./.venv/bin/python scripts_seed.py
./.venv/bin/uvicorn app.main:app --reload

# 3. Worker (separate shell)
./.venv/bin/celery -A app.workers.celery_app.celery_app worker -l info

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
cd ../web && npx tsc --noEmit && npm run build
```

## Evaluation

```bash
cd apps/api
./.venv/bin/python ../../ai/evaluation/runners/eval_complaints.py
```

Requires a real key. Reports land in `ai/evaluation/reports/`. No accuracy is
claimed anywhere in this repo without a report to back it.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — full system design
- [`docs/adr/`](docs/adr/) — architecture decision records
