"""
FastAPI application entry point — Adaptive Learning Coach
=========================================================

This file:
  - Creates the FastAPI app instance.
  - Registers global exception handlers (Pydantic validation, unhandled exceptions).
  - Mounts all routers for Workflow 1.
  - Exposes a lifespan context for startup/shutdown tasks.

No business logic lives here.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers.progress import router as progress_router
from app.schemas.progress import ErrorDetail, ErrorResponse

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown tasks."""
    settings = get_settings()
    log.info(
        "Adaptive Learning Coach starting — env=%s debug=%s",
        settings.app_env,
        settings.app_debug,
    )
    yield
    log.info("Adaptive Learning Coach shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Adaptive Learning Coach — Workflow 1",
        description=(
            "Learner State & Dataset Management API.\n\n"
            "Maintains accurate, queryable learner records and activity history "
            "so that Workflow 2 (Performance Analysis) can retrieve sufficient "
            "context for adaptive reasoning."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.app_debug,
        lifespan=lifespan,
    )

    # ── Global exception handlers ─────────────────────────────────────────

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Convert Pydantic v2 validation errors to the standard error envelope.
        Returns 422 with human-readable field-level messages.
        Never exposes internal stack details.
        """
        field_errors: dict[str, Any] = {}
        for error in exc.errors():
            # loc is a tuple like ('body', 'score') — join to a dotted path
            loc = ".".join(str(part) for part in error.get("loc", []))
            field_errors[loc] = error.get("msg", "Invalid value")

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="VALIDATION_ERROR",
                    message="Request validation failed. Check the 'details' field for per-field errors.",
                    details=field_errors,
                )
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Last-resort handler.  Logs the full traceback server-side but returns
        only a safe, generic message to the caller — no stack traces leaked.
        """
        log.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error=ErrorDetail(
                    code="INTERNAL_SERVER_ERROR",
                    message="An unexpected error occurred. Please try again later.",
                    details={},
                )
            ).model_dump(),
        )

    # ── Routers ───────────────────────────────────────────────────────────
    app.include_router(progress_router)

    # ── Health check ──────────────────────────────────────────────────────
    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health() -> dict:
        return {"status": "ok", "service": "adaptive-learning-coach-workflow-1"}

    return app


# Module-level app instance (used by uvicorn and tests)
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
