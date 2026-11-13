"""FastAPI application. Importing this module boots only a local paper configuration."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from veytrix_api import __version__
from veytrix_api.db import create_db_engine
from veytrix_api.logging_config import configure_logging
from veytrix_api.middleware import CorrelationMiddleware, RateLimitMiddleware
from veytrix_api.ratelimit import ProcessLocalRateLimiter
from veytrix_api.routers import (
    agency,
    agents,
    audit,
    futures,
    market,
    paper_swaps,
    portfolio,
    providers,
    reconciliation,
    research,
    risk,
    strategies,
    supervisor,
    system,
    treasury,
)
from veytrix_api.settings import LOCAL_ORIGINS, Settings, assert_boot_allowed, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    active = settings if settings is not None else get_settings()
    assert_boot_allowed(active)
    configure_logging(active.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        app.state.engine.dispose()

    app = FastAPI(
        title="Veytrix API",
        version=__version__,
        description=(
            "Private personal research API. "
            "This service does not submit orders and is not investment advice. "
            "MAC-01 status is read from a local ledger; only its CLI runner can submit "
            "orders of at most $100 to the user's Alpaca Trading API account (paper, or live "
            "behind the runner's live gate). "
            "Paper swaps are simulated testnet fills priced from read-only market data. "
            "Only the paper-swap CLI records one. This API does not sign or broadcast. "
            "Authentication is not configured."
        ),
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = active
    app.state.engine = create_db_engine(active)
    app.state.limiter = ProcessLocalRateLimiter(active.rate_limit_per_minute)

    router = APIRouter(prefix="/api/v1")
    router.include_router(system.router)
    router.include_router(agents.router)
    router.include_router(supervisor.router)
    router.include_router(agency.router)
    router.include_router(market.router)
    router.include_router(futures.router)
    router.include_router(risk.router)
    router.include_router(portfolio.router)
    router.include_router(research.router)
    router.include_router(audit.router)
    router.include_router(treasury.router)
    router.include_router(strategies.router)
    router.include_router(reconciliation.router)
    router.include_router(paper_swaps.router)
    router.include_router(providers.router)
    app.include_router(router)

    app.add_middleware(RateLimitMiddleware, limiter=app.state.limiter)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(LOCAL_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-Correlation-ID"],
        max_age=600,
    )
    return app


app = create_app()
