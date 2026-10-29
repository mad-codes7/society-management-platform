from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class OwnershipCreate(BaseModel):
    unit_id: UUID
    person_id: UUID
    ownership_type: Optional[str] = Field(default=None, max_length=30)
    share_percentage: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    start_date: str
    end_date: Optional[str] = None


class OwnershipUpdate(BaseModel):
    ownership_type: Optional[str] = Field(default=None, max_length=30)
    share_percentage: Optional[Decimal] = Field(
        default=None, ge=0, le=100, max_digits=5, decimal_places=2
    )
    end_date: Optional[str] = None


class OwnershipTransfer(BaseModel):
    receiving_person_id: UUID
    transfer_date: str


class OwnershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ownership_id: UUID
    society_id: UUID
    unit_id: UUID
    person_id: UUID
    ownership_type: Optional[str]
    share_percentage: Optional[Decimal]
    start_date: date
    end_date: Optional[date]
    status: str
    created_at: datetime
    updated_at: datetime


class OwnershipTransferResponse(BaseModel):
    previous_ownership: OwnershipResponse
    new_ownership: OwnershipResponse
