from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_tenant_context
from app.models.rbac import Permission, RolePermission, UserRole


def require_permission(permission_code: str):
    """
    Require a permission within the requested society.

    The society_id is taken from the API request and resolved through
    the existing tenant-context dependency.
    """

    def permission_dependency(
        society_id: UUID,
        tenant_context: TenantContext = Depends(get_tenant_context),
        db: Session = Depends(get_db),
    ):
        # Platform Super Admin has platform-level access.
        if tenant_context.membership_id is None:
            return tenant_context

        statement = (
            select(Permission.permission_id)
            .join(
                RolePermission,
                RolePermission.permission_id == Permission.permission_id,
            )
            .join(
                UserRole,
                UserRole.role_id == RolePermission.role_id,
            )
            .where(
                UserRole.membership_id == tenant_context.membership_id,
                Permission.code == permission_code,
            )
        )

        permission_exists = db.scalar(statement)

        if permission_exists is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions.",
            )

        return tenant_context

    return permission_dependency