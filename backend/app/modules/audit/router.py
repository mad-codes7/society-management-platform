from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    TenantContext,
    get_current_user,
    resolve_tenant_context,
)
from app.core.rbac import require_permission
from app.models.user import User
from app.modules.audit.schemas import AuditLogListResponse
from app.modules.audit.service import AuditService


router = APIRouter(prefix="/api/v1/audit-logs", tags=["Audit Logs"])
service = AuditService()


def get_audit_context(
    society_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext | None:
    if current_user.is_super_admin:
        return None
    if society_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="society_id is required for society-scoped audit access.",
        )
    tenant_context = resolve_tenant_context(db, current_user, society_id)
    require_permission("audit:read")(
        society_id=society_id,
        tenant_context=tenant_context,
        db=db,
    )
    return tenant_context


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    society_id: Optional[UUID] = Query(default=None),
    action: Optional[str] = Query(default=None, min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    tenant_context: TenantContext | None = Depends(get_audit_context),
) -> AuditLogListResponse:
    scoped_society_id = tenant_context.society_id if tenant_context else society_id
    logs, total = service.list_logs(
        db,
        society_id=scoped_society_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        items=logs,
        total=total,
        limit=limit,
        offset=offset,
    )