from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Building Schemas
class BuildingCreate(BaseModel):
    society_id: UUID
    name: str = Field(min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=30)
    building_type: Optional[str] = Field(default=None, max_length=30)
    total_floors: Optional[int] = Field(default=None, ge=1, le=200)
    status: str = Field(default="ACTIVE", max_length=20)


class BuildingUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=30)
    building_type: Optional[str] = Field(default=None, max_length=30)
    total_floors: Optional[int] = Field(default=None, ge=1, le=200)
    status: Optional[str] = Field(default=None, max_length=20)


class BuildingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    building_id: UUID
    society_id: UUID
    name: str
    code: Optional[str]
    building_type: Optional[str]
    total_floors: Optional[int]
    status: str
    created_at: datetime
    updated_at: datetime


# Floor Schemas
class FloorCreate(BaseModel):
    building_id: UUID
    floor_number: int
    name: Optional[str] = Field(default=None, max_length=50)


class FloorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    floor_id: UUID
    building_id: UUID
    floor_number: int
    name: Optional[str]
    created_at: datetime
    updated_at: datetime


# UnitType Schemas
class UnitTypeCreate(BaseModel):
    society_id: UUID
    name: str = Field(min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=200)
    default_area: Optional[float] = None
    area_unit: Optional[str] = Field(default=None, max_length=20)
    is_active: bool = True


class UnitTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_type_id: UUID
    society_id: UUID
    name: str
    description: Optional[str]
    default_area: Optional[float]
    area_unit: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# Unit Schemas
class UnitCreate(BaseModel):
    society_id: UUID
    building_id: UUID
    floor_id: UUID
    unit_type_id: Optional[UUID] = None
    unit_number: str = Field(min_length=1, max_length=30)
    area: Optional[float] = None
    occupancy_status: str = Field(default="VACANT", max_length=20)


class UnitUpdate(BaseModel):
    unit_type_id: Optional[UUID] = None
    occupancy_status: Optional[str] = Field(default=None, max_length=20)


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_id: UUID
    society_id: UUID
    building_id: UUID
    floor_id: UUID
    unit_type_id: Optional[UUID]
    unit_number: str
    occupancy_status: str
    created_at: datetime
    updated_at: datetime
