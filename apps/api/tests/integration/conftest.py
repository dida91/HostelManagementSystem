from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

API_DIR = Path(__file__).resolve().parents[2]


def _run(*cmd: str) -> None:
    result = subprocess.run(
        list(cmd), cwd=API_DIR, env=os.environ.copy(), capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{result.stdout}\n{result.stderr}")


@pytest.fixture(scope="session", autouse=True)
def _fresh_database() -> Iterator[None]:
    """Drop and recreate the test database, migrate it, and seed it.

    The root conftest has already pointed DATABASE_URL at it. Migrations and
    the seed run as the real CLI commands, exactly as a deployment would.
    """
    url = make_url(os.environ["DATABASE_URL_SYNC"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    admin.dispose()

    _run(str(API_DIR / ".venv" / "bin" / "alembic"), "upgrade", "head")
    _run(sys.executable, "scripts_seed.py")
    yield
