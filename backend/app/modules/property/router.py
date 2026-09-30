from __future__ import annotations
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    TenantContext,
    get_current_user,
    get_tenant_context,
    resolve_tenant_context,
)
from app.models.user import User
from app.modules.property.schemas import (
    BuildingCreate,
    BuildingResponse,
    FloorResponse,
    UnitCreate,
    UnitResponse,
    UnitTypeCreate,
    UnitTypeResponse,
    UnitUpdate,
)
from app.modules.property.service import PropertyService

router = APIRouter(
    prefix="/api/v1/properties",
    tags=["Properties & Master Data"],
    dependencies=[Depends(get_current_user)],
)

service = PropertyService()


# Building Endpoints
@router.post(
    "/buildings",
    response_model=BuildingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_building(
    data: BuildingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolve_tenant_context(db, current_user, data.society_id)
    return service.create_building(db, data)


@router.get(
    "/societies/{society_id}/buildings",
    response_model=List[BuildingResponse],
)
def list_buildings(
    society_id: UUID,
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(get_tenant_context),
):
    return service.list_buildings(db, tenant_context.society_id)


# Floor Endpoints
@router.get(
    "/buildings/{building_id}/floors",
    response_model=List[FloorResponse],
)
def list_floors(
    building_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    building = service.get_building_by_id(db, building_id)
    if building is not None:
        resolve_tenant_context(db, current_user, building.society_id)
    return service.list_floors(db, building_id)


# UnitType Endpoints
@router.post(
    "/unit-types",
    response_model=UnitTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_unit_type(
    data: UnitTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolve_tenant_context(db, current_user, data.society_id)
    return service.create_unit_type(db, data)


@router.get(
    "/societies/{society_id}/unit-types",
    response_model=List[UnitTypeResponse],
)
def list_unit_types(
    society_id: UUID,
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(get_tenant_context),
):
    return service.list_unit_types(db, tenant_context.society_id)


# Unit Endpoints
@router.post(
    "/units",
    response_model=UnitResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_unit(
    data: UnitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolve_tenant_context(db, current_user, data.society_id)
    return service.create_unit(db, data)


@router.get(
    "/societies/{society_id}/units",
    response_model=List[UnitResponse],
)
def list_units(
    society_id: UUID,
    building_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(get_tenant_context),
):
    return service.list_units(db, tenant_context.society_id, building_id)


@router.patch(
    "/units/{unit_id}",
    response_model=UnitResponse,
)
def update_unit(
    unit_id: UUID,
    data: UnitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    unit = service.get_unit_by_id(db, unit_id)
    if unit is not None:
        resolve_tenant_context(db, current_user, unit.society_id)
    return service.update_unit(db, unit_id, data)
