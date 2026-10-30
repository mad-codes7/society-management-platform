from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_current_user
from app.core.rbac import require_permission
from app.models.user import User
from app.modules.ownership.schemas import (
    OwnershipCreate,
    OwnershipResponse,
    OwnershipTransfer,
    OwnershipTransferResponse,
    OwnershipUpdate,
)
from app.modules.ownership.service import ownership_service

router = APIRouter(
    prefix="/api/v1/ownerships",
    tags=["Ownership History"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/societies/{society_id}",
    response_model=OwnershipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ownership(
    society_id: UUID,
    data: OwnershipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return ownership_service.create(
        db,
        tenant_context.society_id,
        data,
        current_user.user_id,
    )


@router.get(
    "/societies/{society_id}",
    response_model=list[OwnershipResponse],
)
def list_ownerships(
    society_id: UUID,
    unit_id: Optional[UUID] = Query(default=None),
    person_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("property:read")),
):
    return ownership_service.list(
        db,
        tenant_context.society_id,
        unit_id,
        person_id,
    )


@router.get(
    "/societies/{society_id}/{ownership_id}",
    response_model=OwnershipResponse,
)
def get_ownership(
    society_id: UUID,
    ownership_id: UUID,
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("property:read")),
):
    return ownership_service.get(db, tenant_context.society_id, ownership_id)


@router.patch(
    "/societies/{society_id}/{ownership_id}",
    response_model=OwnershipResponse,
)
def update_ownership(
    society_id: UUID,
    ownership_id: UUID,
    data: OwnershipUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return ownership_service.update(
        db,
        tenant_context.society_id,
        ownership_id,
        data,
        current_user.user_id,
    )


@router.post(
    "/societies/{society_id}/{ownership_id}/transfer",
    response_model=OwnershipTransferResponse,
)
def transfer_ownership(
    society_id: UUID,
    ownership_id: UUID,
    data: OwnershipTransfer,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    source, receiving = ownership_service.transfer(
        db,
        tenant_context.society_id,
        ownership_id,
        data,
        current_user.user_id,
    )
    return OwnershipTransferResponse(
        previous_ownership=source,
        new_ownership=receiving,
    )
