from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OccupancyCheckIn(BaseModel):
    unit_id: UUID
    person_id: UUID
    occupancy_type: str = Field(min_length=1, max_length=20)
    move_in_date: str


class OccupancyCheckOut(BaseModel):
    move_out_date: str


class OccupancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    occupancy_id: UUID
    society_id: UUID
    unit_id: UUID
    person_id: UUID
    occupancy_type: str
    move_in_date: date
    move_out_date: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime
