"""FastAPI dependencies: authentication, role gates, AI provider injection."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import EmbeddingProvider, LLMProvider
from app.ai.providers.registry import get_embedding_provider, get_llm_provider
from app.ai.tools.registry import Principal
from app.core.db import get_session
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.logging import user_id_ctx
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.user import Student, User

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    request: Request,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    token: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    else:
        # The Next.js BFF forwards the session as an httpOnly cookie.
        token = request.cookies.get("access_token")

    if not token:
        raise AuthenticationError()

    payload = decode_token(token, expected_type="access")
    user = (
        await session.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError()

    user_id_ctx.set(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole):  # type: ignore[no-untyped-def]
    """Role gate. Applied at the router, and independently re-checked by the
    tool registry for anything the assistant can reach."""

    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise PermissionDeniedError()
        return user

    return _check


RequireStaff = Depends(require_roles(UserRole.STAFF, UserRole.WARDEN, UserRole.SUPER_ADMIN))
RequireWarden = Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))
RequireAdmin = Depends(require_roles(UserRole.SUPER_ADMIN))


async def get_principal(user: CurrentUser, session: SessionDep) -> Principal:
    """Build the identity the AI tool layer will use.

    This is the ONLY source of identity for tool execution -- never model output.
    """
    student_id = (
        await session.execute(select(Student.id).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    return Principal(user_id=user.id, role=user.role, student_id=student_id)


PrincipalDep = Annotated[Principal, Depends(get_principal)]


def rate_limit(bucket: str):  # type: ignore[no-untyped-def]
    """Per-user (or per-IP when unauthenticated) rate limit for a bucket."""

    async def _check(request: Request) -> None:
        from app.core.ratelimit import enforce_rate_limit

        identity = user_id_ctx.get() or (request.client.host if request.client else "anonymous")
        await enforce_rate_limit(key=identity, bucket=bucket)

    return _check


def llm_provider() -> LLMProvider:
    return get_llm_provider()


def embedding_provider() -> EmbeddingProvider:
    return get_embedding_provider()


LLMDep = Annotated[LLMProvider, Depends(llm_provider)]
EmbeddingDep = Annotated[EmbeddingProvider, Depends(embedding_provider)]
