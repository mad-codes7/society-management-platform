from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import settings


ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 12
password_hash = PasswordHash.recommended()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": subject,
        "token_type": "access",
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        algorithms=[ALGORITHM],
        options={"require": ["sub", "token_type", "iat", "exp"]},
    )

    if payload.get("token_type") != "access":
        raise InvalidTokenError("Invalid access-token type")

    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise InvalidTokenError("Invalid subject")

    try:
        UUID(subject)
    except ValueError as error:
        raise InvalidTokenError("Invalid subject") from error

    return payload
