"""Authentication: login, refresh rotation with reuse detection, logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError, ValidationFailedError
from app.core.logging import get_logger
from app.core.security import (
    create_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)
from app.models.user import RefreshToken, Student, User
from app.services.notifications import NotificationService, password_changed_message

log = get_logger("auth")


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> tuple[User, str, str]:
        user = (
            await self._session.execute(select(User).where(User.email == email.lower().strip()))
        ).scalar_one_or_none()

        # Always run a verification to keep timing uniform whether or not the
        # account exists, so the endpoint cannot be used to enumerate users.
        stored = user.password_hash if user else "$argon2id$v=19$m=65536,t=3,p=4$" + "A" * 22
        ok = verify_password(password, stored)

        if user is None or not ok or not user.is_active:
            log.info("login_failed", email_domain=email.split("@")[-1] if "@" in email else None)
            raise AuthenticationError("Incorrect email or password.")

        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        user.last_login_at = datetime.now(UTC)
        access, refresh = await self._issue_pair(user, user_agent=user_agent, ip=ip)
        log.info("login_succeeded", user_id=str(user.id), role=user.role.value)
        return user, access, refresh

    async def _issue_pair(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip: str | None = None,
        replaces_jti: str | None = None,
    ) -> tuple[str, str]:
        access, _, _ = create_token(subject=str(user.id), token_type="access", role=user.role.value)
        refresh, expires_at, jti = create_token(subject=str(user.id), token_type="refresh")
        self._session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_refresh_token(refresh),
                jti=jti,
                expires_at=expires_at,
                user_agent=(user_agent or "")[:255],
                ip_address=ip,
            )
        )
        if replaces_jti:
            await self._session.execute(
                update(RefreshToken)
                .where(RefreshToken.jti == replaces_jti)
                .values(replaced_by_jti=jti, revoked_at=datetime.now(UTC))
            )
        await self._session.flush()
        return access, refresh

    async def refresh(
        self, *, refresh_token: str, user_agent: str | None = None, ip: str | None = None
    ) -> tuple[User, str, str]:
        """Rotate a refresh token.

        Reuse detection: presenting an already-rotated token means the token was
        captured, so every session for that user is revoked rather than silently
        issuing a new pair.
        """
        payload = decode_token(refresh_token, expected_type="refresh")
        token_hash = hash_refresh_token(refresh_token)
        record = (
            await self._session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()

        if record is None:
            raise AuthenticationError("Invalid credentials.")

        if record.revoked_at is not None or record.replaced_by_jti is not None:
            log.warning("refresh_token_reuse_detected", user_id=str(record.user_id))
            await self._session.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == record.user_id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
            raise AuthenticationError("Session is no longer valid. Please sign in again.")

        if record.expires_at <= datetime.now(UTC):
            raise AuthenticationError("Session expired. Please sign in again.")

        user = (
            await self._session.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
        ).scalar_one_or_none()
        if user is None or not user.is_active:
            raise AuthenticationError("Invalid credentials.")

        access, new_refresh = await self._issue_pair(
            user, user_agent=user_agent, ip=ip, replaces_jti=record.jti
        )
        return user, access, new_refresh

    async def logout(self, *, refresh_token: str) -> None:
        token_hash = hash_refresh_token(refresh_token)
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def revoke_all_sessions(self, user_id: uuid.UUID) -> None:
        """Sign a user out everywhere. Access tokens are short-lived and are
        also refused as soon as the account is inactive."""
        await self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    async def change_password(
        self,
        *,
        user: User,
        current_password: str,
        new_password: str,
        user_agent: str | None = None,
        ip: str | None = None,
    ) -> tuple[str, str]:
        """Change one's own password.

        Every other session is signed out; the caller gets a fresh token pair
        so they stay signed in on this device.
        """
        if not verify_password(current_password, user.password_hash):
            log.info("password_change_rejected", user_id=str(user.id))
            raise ValidationFailedError("Your current password is incorrect.")
        if verify_password(new_password, user.password_hash):
            raise ValidationFailedError("The new password must differ from the current one.")

        user.password_hash = hash_password(new_password)
        await self.revoke_all_sessions(user.id)
        access, refresh = await self._issue_pair(user, user_agent=user_agent, ip=ip)

        await NotificationService(self._session).notify(
            [user.id], password_changed_message(by_staff=False)
        )
        log.info("password_changed", user_id=str(user.id))
        return access, refresh

    async def purge_expired_refresh_tokens(self, *, now: datetime) -> int:
        """Delete refresh tokens past their expiry.

        Safe for reuse detection: an expired token is rejected when its JWT is
        decoded (the row and the JWT share one expiry), before its row would
        ever be looked up.
        """
        result = await self._session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def student_id_for(self, user_id: uuid.UUID) -> uuid.UUID | None:
        return (
            await self._session.execute(select(Student.id).where(Student.user_id == user_id))
        ).scalar_one_or_none()
