"""A scratch Postgres database for the communication tests.

Same rules as `test_schema.py`: never touch port 5432 outside CI (on this machine that is
daypilot-db), and skip when Postgres is not reachable. The scratch database is
`veytrix_comms_test` on the same server, rebuilt with `alembic upgrade head`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = "veytrix_comms_test"
DEFAULT = "postgresql+psycopg://veytrix:local-dev-only@127.0.0.1:5432/veytrix"


def _swap(url: str, database: str) -> str:
    base, _, query = url.partition("?")
    prefix, _current = base.rsplit("/", 1)
    swapped = f"{prefix}/{database}"
    return f"{swapped}?{query}" if query else swapped


def _reachable(url: str) -> bool:
    import psycopg

    try:
        with psycopg.connect(
            url.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=2
        ):
            return True
    except Exception:
        return False


def scratch_database() -> str:
    """Return the scratch URL after migrating it, or skip the calling test module."""

    source = os.environ.get("DATABASE_URL", DEFAULT)
    ci = os.environ.get("CI") == "true"
    if not ci and ":5432/" in source:
        pytest.skip("Refusing port 5432 outside CI. Set DATABASE_URL to 127.0.0.1:5433.")
    admin = _swap(source, "postgres")
    if not _reachable(admin):
        if ci:
            pytest.fail("PostgreSQL was not reachable for the communication tests.")
        pytest.skip("PostgreSQL is not running locally.")

    import psycopg
    from alembic import command
    from alembic.config import Config

    from veytrix_api.settings import get_settings

    url = _swap(source, SCRATCH)
    raw_admin = admin.replace("postgresql+psycopg://", "postgresql://", 1)
    raw_test = url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(raw_admin, autocommit=True, connect_timeout=2) as connection:
        if (
            connection.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (SCRATCH,)
            ).fetchone()
            is None
        ):
            connection.execute(f"CREATE DATABASE {SCRATCH}")
    with psycopg.connect(raw_test, autocommit=True, connect_timeout=2) as connection:
        connection.execute("DROP SCHEMA IF EXISTS private CASCADE")
        connection.execute("DROP SCHEMA public CASCADE")
        connection.execute("CREATE SCHEMA public")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", url)
        patch.setenv("VEYTRIX_ENV", "local")
        patch.setenv("VEYTRIX_ENABLE_LIVE_BROKER", "0")
        get_settings.cache_clear()
        try:
            command.upgrade(Config(str(ROOT / "services/api/alembic.ini")), "head")
        finally:
            get_settings.cache_clear()
    return url
