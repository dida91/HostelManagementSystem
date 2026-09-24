from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.schemas.common import LoginRequest, MeOut, PasswordChange, TokenResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
ACCESS_COOKIE = "access_token"


def _set_session_cookies(response: Response, access: str, refresh: str) -> None:
    """httpOnly + SameSite=Strict: the browser never exposes these to JS, so an
    XSS bug cannot exfiltrate a session."""
    secure = get_settings().app_env != "local"
    s = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=s.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=s.refresh_token_ttl_days * 86400,
        path="/",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    # Throttles credential stuffing against the resident directory.
    dependencies=[Depends(rate_limit("auth"))],
)
async def login(
    payload: LoginRequest, request: Request, response: Response, session: SessionDep
) -> TokenResponse:
    service = AuthService(session)
    _, access, refresh = await service.authenticate(
        email=payload.email,
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    _set_session_cookies(response, access, refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, response: Response, session: SessionDep) -> TokenResponse:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        body = (
            await request.json()
            if request.headers.get("content-type") == "application/json"
            else {}
        )
        token = body.get("refresh_token")
    if not token:
        raise AuthenticationError()
    service = AuthService(session)
    _, access, new_refresh = await service.refresh(
        refresh_token=token,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    _set_session_cookies(response, access, new_refresh)
    return TokenResponse(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: SessionDep) -> None:
    if token := request.cookies.get(REFRESH_COOKIE):
        await AuthService(session).logout(refresh_token=token)
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.post(
    "/change-password",
    response_model=TokenResponse,
    # Same throttle as login: this endpoint also verifies a password.
    dependencies=[Depends(rate_limit("auth"))],
)
async def change_password(
    payload: PasswordChange,
    user: CurrentUser,
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenResponse:
    """Change your own password. Every other session is signed out; this one
    continues with a fresh token pair."""
    access, refresh = await AuthService(session).change_password(
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        user_agent=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    _set_session_cookies(response, access, refresh)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, session: SessionDep) -> MeOut:
    from sqlalchemy import select

    from app.models.user import Student

    row = (
        await session.execute(select(Student).where(Student.user_id == user.id))
    ).scalar_one_or_none()
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        student_id=row.id if row else None,
        student_code=row.student_code if row else None,
    )
