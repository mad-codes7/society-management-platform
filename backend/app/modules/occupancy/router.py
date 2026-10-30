from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_current_user
from app.core.rbac import require_permission
from app.models.user import User
from app.modules.occupancy.schemas import (
    OccupancyCheckIn,
    OccupancyCheckOut,
    OccupancyResponse,
)
from app.modules.occupancy.service import occupancy_service

router = APIRouter(
    prefix="/api/v1/occupancies",
    tags=["Occupancy History"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/societies/{society_id}",
    response_model=OccupancyResponse,
    status_code=status.HTTP_201_CREATED,
)
def check_in(
    society_id: UUID,
    data: OccupancyCheckIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("resident:manage")),
):
    return occupancy_service.check_in(
        db,
        tenant_context.society_id,
        data,
        current_user.user_id,
    )


@router.post(
    "/societies/{society_id}/{occupancy_id}/check-out",
    response_model=OccupancyResponse,
)
def check_out(
    society_id: UUID,
    occupancy_id: UUID,
    data: OccupancyCheckOut,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("resident:manage")),
):
    return occupancy_service.check_out(
        db,
        tenant_context.society_id,
        occupancy_id,
        data.move_out_date,
        current_user.user_id,
    )


@router.get(
    "/societies/{society_id}",
    response_model=list[OccupancyResponse],
)
def list_occupancies(
    society_id: UUID,
    unit_id: Optional[UUID] = Query(default=None),
    person_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("resident:read")),
):
    return occupancy_service.list(
        db,
        tenant_context.society_id,
        unit_id,
        person_id,
    )


@router.get(
    "/societies/{society_id}/{occupancy_id}",
    response_model=OccupancyResponse,
)
def get_occupancy(
    society_id: UUID,
    occupancy_id: UUID,
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("resident:read")),
):
    return occupancy_service.get(db, tenant_context.society_id, occupancy_id)
