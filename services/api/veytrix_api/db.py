"""SQLAlchemy session for the local Postgres baseline."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from veytrix_api.settings import Settings


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 2},
    )


def get_db(request: Request) -> Iterator[Session]:
    session = Session(request.app.state.engine)
    try:
        yield session
    finally:
        session.close()
