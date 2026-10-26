from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import TenantContext, get_current_user
from app.core.rbac import require_permission
from app.models.user import User
from app.modules.vehicles.schemas import VehicleCreate, VehicleResponse, VehicleUpdate
from app.modules.vehicles.service import vehicle_service

router = APIRouter(
    prefix="/api/v1/vehicles",
    tags=["Vehicles"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/societies/{society_id}",
    response_model=VehicleResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_vehicle(
    society_id: UUID,
    data: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return vehicle_service.register(
        db,
        tenant_context.society_id,
        data,
        current_user.user_id,
    )


@router.get(
    "/societies/{society_id}",
    response_model=list[VehicleResponse],
)
def list_vehicles(
    society_id: UUID,
    unit_id: Optional[UUID] = Query(default=None),
    person_id: Optional[UUID] = Query(default=None),
    vehicle_status: Optional[str] = Query(default=None, alias="status", max_length=20),
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("property:read")),
):
    return vehicle_service.list(
        db,
        tenant_context.society_id,
        unit_id,
        person_id,
        vehicle_status,
    )


@router.get(
    "/societies/{society_id}/{vehicle_id}",
    response_model=VehicleResponse,
)
def get_vehicle(
    society_id: UUID,
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(require_permission("property:read")),
):
    return vehicle_service.get(db, tenant_context.society_id, vehicle_id)


@router.patch(
    "/societies/{society_id}/{vehicle_id}",
    response_model=VehicleResponse,
)
def update_vehicle(
    society_id: UUID,
    vehicle_id: UUID,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return vehicle_service.update(
        db,
        tenant_context.society_id,
        vehicle_id,
        data,
        current_user.user_id,
    )


@router.post(
    "/societies/{society_id}/{vehicle_id}/deactivate",
    response_model=VehicleResponse,
)
def deactivate_vehicle(
    society_id: UUID,
    vehicle_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_context: TenantContext = Depends(require_permission("property:manage")),
):
    return vehicle_service.deactivate(
        db,
        tenant_context.society_id,
        vehicle_id,
        current_user.user_id,
    )
