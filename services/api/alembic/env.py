"""Alembic environment. Migrations run only for a local paper configuration."""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import create_engine, pool

REPO_ROOT = Path(__file__).resolve().parents[3]
for _relative in ("services/api", "services/market-data", "services/risk", "services/quant"):
    _path = str(REPO_ROOT / _relative)
    if _path not in sys.path:
        sys.path.insert(0, _path)

from veytrix_api.models import Base  # noqa: E402
from veytrix_api.settings import assert_boot_allowed, get_settings  # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    settings = get_settings()
    assert_boot_allowed(settings)
    if settings.veytrix_env != "local":
        raise RuntimeError("Alembic refuses to run unless VEYTRIX_ENV=local.")
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(_database_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
