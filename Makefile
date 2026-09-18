.PHONY: up down api worker web test lint types migrate seed check

up:      ; docker compose -f infrastructure/docker-compose.yml up -d
down:    ; docker compose -f infrastructure/docker-compose.yml down
api:     ; cd apps/api && ./.venv/bin/uvicorn app.main:app --reload
worker:  ; cd apps/api && ./.venv/bin/celery -A app.workers.celery_app.celery_app worker -l info
web:     ; cd apps/web && npm run dev
migrate: ; cd apps/api && ./.venv/bin/alembic upgrade head
seed:    ; cd apps/api && ./.venv/bin/python scripts_seed.py
test:    ; cd apps/api && ./.venv/bin/python -m pytest tests/ -q
lint:    ; cd apps/api && ./.venv/bin/ruff check app tests && ./.venv/bin/ruff format --check app tests
types:   ; cd apps/api && ./.venv/bin/mypy app

# Everything CI runs, locally.
check: lint types
	cd apps/api && ./.venv/bin/alembic check && ./.venv/bin/python -m pytest tests/ -q
	cd apps/web && npx tsc --noEmit
