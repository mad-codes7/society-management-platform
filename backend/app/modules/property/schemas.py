from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# Building Schemas
class BuildingCreate(BaseModel):
    society_id: UUID
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=20)
    building_type: str = Field(default="TOWER", max_length=20)
    total_floors: int = Field(default=1, ge=1)


class BuildingUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    code: Optional[str] = Field(default=None, max_length=20)
    building_type: Optional[str] = Field(default=None, max_length=20)
    total_floors: Optional[int] = Field(default=None, ge=1)


class BuildingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    building_id: UUID
    society_id: UUID
    name: str
    code: str
    building_type: str
    total_floors: int
    created_at: datetime
    updated_at: datetime


# Floor Schemas
class FloorCreate(BaseModel):
    building_id: UUID
    floor_number: int
    floor_name: Optional[str] = Field(default=None, max_length=50)


class FloorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    floor_id: UUID
    building_id: UUID
    floor_number: int
    floor_name: Optional[str]
    created_at: datetime
    updated_at: datetime


# UnitType Schemas
class UnitTypeCreate(BaseModel):
    society_id: UUID
    name: str = Field(min_length=1, max_length=100)
    super_builtup_area: Optional[float] = None
    carpet_area: Optional[float] = None


class UnitTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_type_id: UUID
    society_id: UUID
    name: str
    super_builtup_area: Optional[float]
    carpet_area: Optional[float]
    created_at: datetime
    updated_at: datetime


# Unit Schemas
class UnitCreate(BaseModel):
    society_id: UUID
    building_id: UUID
    floor_id: UUID
    unit_type_id: Optional[UUID] = None
    unit_number: str = Field(min_length=1, max_length=20)
    occupancy_status: str = Field(default="VACANT", max_length=20)
    is_commercial: bool = Field(default=False)


class UnitUpdate(BaseModel):
    unit_type_id: Optional[UUID] = None
    occupancy_status: Optional[str] = Field(default=None, max_length=20)
    is_commercial: Optional[bool] = None


class UnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unit_id: UUID
    society_id: UUID
    building_id: UUID
    floor_id: UUID
    unit_type_id: Optional[UUID]
    unit_number: str
    occupancy_status: str
    is_commercial: bool
    created_at: datetime
    updated_at: datetime
