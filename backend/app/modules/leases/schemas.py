from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeaseCreate(BaseModel):
    unit_id: UUID
    tenant_person_id: UUID
    owner_person_id: Optional[UUID] = None
    lease_start: str
    lease_end: Optional[str] = None


class LeaseUpdate(BaseModel):
    owner_person_id: Optional[UUID] = None
    lease_end: Optional[str] = None


class LeaseEnd(BaseModel):
    lease_end: str


class LeaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lease_id: UUID
    society_id: UUID
    unit_id: UUID
    tenant_person_id: UUID
    owner_person_id: Optional[UUID]
    lease_start: date
    lease_end: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime
