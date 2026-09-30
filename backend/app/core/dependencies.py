from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.modules.auth.repository import AuthRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials.strip())
        user_id = UUID(payload["sub"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges.",
        )
    return current_user


@dataclass(frozen=True)
class TenantContext:
    user_id: UUID
    society_id: UUID
    membership_id: Optional[UUID] = None


def resolve_tenant_context(
    db: Session,
    user: User,
    society_id: UUID,
) -> TenantContext:
    if user.is_super_admin:
        return TenantContext(
            user_id=user.user_id,
            society_id=society_id,
        )

    membership = AuthRepository().get_active_membership_for_user_in_society(
        db,
        user.user_id,
        society_id,
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this society.",
        )

    return TenantContext(
        user_id=user.user_id,
        society_id=society_id,
        membership_id=membership.membership_id,
    )


def get_tenant_context(
    society_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    return resolve_tenant_context(db, user, society_id)
