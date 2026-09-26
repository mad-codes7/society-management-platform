from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SocietyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    registration_no: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = None
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    contact_email: Optional[EmailStr] = None
    logo_path: Optional[str] = Field(default=None, max_length=500)


class SocietyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    registration_no: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = None
    contact_phone: Optional[str] = Field(default=None, max_length=20)
    contact_email: Optional[EmailStr] = None
    logo_path: Optional[str] = Field(default=None, max_length=500)


class SocietyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    society_id: UUID
    name: str
    registration_no: Optional[str]
    address: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    logo_path: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime


class SocietyListResponse(BaseModel):
    items: List[SocietyResponse]
    total: int
    limit: int
    offset: int