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
from app.modules.residents.schemas import (
    EmergencyContactCreate,
    EmergencyContactResponse,
    FamilyMemberCreate,
    FamilyMemberResponse,
    ResidentCreate,
    ResidentResponse,
)
from app.modules.residents.service import ResidentService

router = APIRouter(
    prefix="/api/v1/residents",
    tags=["Residents & People Master"],
    dependencies=[Depends(get_current_user)],
)

service = ResidentService()


@router.post(
    "",
    response_model=ResidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_resident(
    data: ResidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolve_tenant_context(db, current_user, data.society_id)
    return service.create_resident(db, data)


@router.get(
    "/societies/{society_id}",
    response_model=List[ResidentResponse],
)
def list_residents(
    society_id: UUID,
    unit_id: Optional[UUID] = Query(default=None),
    db: Session = Depends(get_db),
    tenant_context: TenantContext = Depends(get_tenant_context),
):
    return service.list_residents(db, tenant_context.society_id, unit_id)


# Family Member endpoints (Static routes declared before generic /{resident_id})
@router.post(
    "/family-members",
    response_model=FamilyMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_family_member(
    data: FamilyMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resident = service.get_resident(db, data.resident_id)
    resolve_tenant_context(db, current_user, resident.society_id)
    return service.add_family_member(db, data)


# Emergency Contact endpoints (Static routes declared before generic /{resident_id})
@router.post(
    "/emergency-contacts",
    response_model=EmergencyContactResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_emergency_contact(
    data: EmergencyContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resident = service.get_resident(db, data.resident_id)
    resolve_tenant_context(db, current_user, resident.society_id)
    return service.add_emergency_contact(db, data)


# Generic Resident ID endpoints
@router.get(
    "/{resident_id}",
    response_model=ResidentResponse,
)
def get_resident(
    resident_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resident = service.get_resident(db, resident_id)
    resolve_tenant_context(db, current_user, resident.society_id)
    return resident


@router.get(
    "/{resident_id}/family-members",
    response_model=List[FamilyMemberResponse],
)
def list_family_members(
    resident_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resident = service.get_resident(db, resident_id)
    resolve_tenant_context(db, current_user, resident.society_id)
    return service.list_family_members(db, resident_id)


@router.get(
    "/{resident_id}/emergency-contacts",
    response_model=List[EmergencyContactResponse],
)
def list_emergency_contacts(
    resident_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resident = service.get_resident(db, resident_id)
    resolve_tenant_context(db, current_user, resident.society_id)
    return service.list_emergency_contacts(db, resident_id)
