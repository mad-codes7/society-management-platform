from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VehicleCreate(BaseModel):
    registration_number: str = Field(min_length=1, max_length=30)
    vehicle_type: str = Field(min_length=1, max_length=30)
    person_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None
    make_model: Optional[str] = Field(default=None, max_length=100)
    colour: Optional[str] = Field(default=None, max_length=40)


class VehicleUpdate(BaseModel):
    registration_number: Optional[str] = Field(
        default=None, min_length=1, max_length=30
    )
    vehicle_type: Optional[str] = Field(default=None, min_length=1, max_length=30)
    person_id: Optional[UUID] = None
    unit_id: Optional[UUID] = None
    make_model: Optional[str] = Field(default=None, max_length=100)
    colour: Optional[str] = Field(default=None, max_length=40)


class VehicleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    vehicle_id: UUID
    society_id: UUID
    person_id: Optional[UUID]
    unit_id: Optional[UUID]
    registration_number: str
    vehicle_type: str
    make_model: Optional[str]
    colour: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
