"""FastAPI application entrypoint."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import ConfigurationError, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_ctx

log = get_logger("app")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(debug=settings.app_debug)

    # Fail fast and loudly on invalid configuration rather than starting a
    # process that looks healthy and breaks on first AI request.
    try:
        settings.validate_for_startup()
    except ConfigurationError as exc:
        log.error("configuration_invalid", detail=str(exc))
        raise

    log.info(
        "startup",
        app_env=settings.app_env,
        ai_configured=settings.ai.is_configured,
        text_model=settings.ai.gemini_text_model,
        embedding_model=settings.ai.gemini_embedding_model,
        embedding_dim=settings.ai.gemini_embedding_dim,
    )
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Kutumba Hostel Management API",
        description="AI-Powered Smart Hostel Management and Data Analytics System",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env != "production" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_ctx.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
