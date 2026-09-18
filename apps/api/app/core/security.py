"""Password hashing and JWT issuance/verification."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import AuthenticationError

_hasher = PasswordHasher()
ALGORITHM = "HS256"
TokenType = Literal["access", "refresh"]


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def create_token(
    *, subject: str, token_type: TokenType, role: str | None = None, jti: str | None = None
) -> tuple[str, datetime, str]:
    """Return (encoded_jwt, expires_at, jti)."""
    s = get_settings()
    now = datetime.now(UTC)
    ttl = (
        timedelta(minutes=s.access_token_ttl_minutes)
        if token_type == "access"
        else timedelta(days=s.refresh_token_ttl_days)
    )
    expires_at = now + ttl
    token_id = jti or str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": token_id,
    }
    if role:
        payload["role"] = role
    encoded = jwt.encode(payload, s.secret_key.get_secret_value(), algorithm=ALGORITHM)
    return encoded, expires_at, token_id


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    s = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, s.secret_key.get_secret_value(), algorithms=[ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expired. Please sign in again.") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid credentials.") from exc
    if payload.get("type") != expected_type:
        raise AuthenticationError("Invalid credentials.")
    return payload


def hash_refresh_token(token: str) -> str:
    """Refresh tokens are stored hashed so a DB leak cannot mint sessions."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_secure_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
