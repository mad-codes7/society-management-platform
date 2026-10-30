from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_current_user
from app.core.rbac import require_permission
from app.models.user import User
from app.modules.leases.schemas import LeaseCreate, LeaseEnd, LeaseResponse, LeaseUpdate
from app.modules.leases.service import lease_service

router = APIRouter(
    prefix="/api/v1/leases",
    tags=["Lease History"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/societies/{society_id}",
    response_model=LeaseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_lease(
    society_id: UUID,
    data: LeaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return lease_service.create(
        db,
        tenant_context.society_id,
        data,
        current_user.user_id,
    )


@router.get(
    "/societies/{society_id}",
    response_model=list[LeaseResponse],
)
def list_leases(
    society_id: UUID,
    unit_id: Optional[UUID] = Query(default=None),
    tenant_person_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("property:read")),
):
    return lease_service.list(
        db,
        tenant_context.society_id,
        unit_id,
        tenant_person_id,
    )


@router.get(
    "/societies/{society_id}/{lease_id}",
    response_model=LeaseResponse,
)
def get_lease(
    society_id: UUID,
    lease_id: UUID,
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("property:read")),
):
    return lease_service.get(db, tenant_context.society_id, lease_id)


@router.patch(
    "/societies/{society_id}/{lease_id}",
    response_model=LeaseResponse,
)
def update_lease(
    society_id: UUID,
    lease_id: UUID,
    data: LeaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return lease_service.update(
        db,
        tenant_context.society_id,
        lease_id,
        data,
        current_user.user_id,
    )


@router.post(
    "/societies/{society_id}/{lease_id}/end",
    response_model=LeaseResponse,
)
def end_lease(
    society_id: UUID,
    lease_id: UUID,
    data: LeaseEnd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return lease_service.end(
        db,
        tenant_context.society_id,
        lease_id,
        data.lease_end,
        current_user.user_id,
    )
