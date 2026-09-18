"""RFC 7807 problem+json error model.

Internal detail (provider messages, SQL, stack traces) never crosses this boundary.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Base class for errors that are safe to surface to a client."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Request could not be processed."

    def __init__(self, message: str | None = None, *, extra: dict[str, Any] | None = None) -> None:
        self.message = message or self.message
        self.extra = extra or {}
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Resource not found."


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    message = "Authentication required."


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "You do not have permission to perform this action."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "The request conflicts with the current state."


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"
    message = "The submitted data is invalid."


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Too many requests. Please slow down."


class AIUnavailableError(AppError):
    """Raised for ANY upstream AI failure.

    The provider's own message is logged, never returned: it can contain model
    names, quota details and request fragments.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "ai_temporarily_unavailable"
    message = "The AI service is temporarily unavailable. Please try again shortly."


def _problem(
    status_code: int, code: str, message: str, extra: dict[str, Any] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"about:blank#{code}",
        "title": code,
        "status": status_code,
        "detail": message,
    }
    if extra:
        body["errors"] = extra
    return JSONResponse(
        status_code=status_code, content=body, media_type="application/problem+json"
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_r: Request, exc: AppError) -> JSONResponse:
        return _problem(exc.status_code, exc.code, exc.message, exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validation(_r: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem(
            422,
            "validation_failed",
            "The submitted data is invalid.",
            {"fields": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]},
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_r: Request, exc: SQLAlchemyError) -> JSONResponse:
        log.error("database_error", error=str(exc), exc_info=True)
        return _problem(500, "internal_error", "An internal error occurred.")

    @app.exception_handler(Exception)
    async def _unhandled(_r: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", error=str(exc), exc_info=True)
        return _problem(500, "internal_error", "An internal error occurred.")
