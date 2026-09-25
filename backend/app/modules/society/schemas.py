from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SocietyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    registration_no: str | None = Field(default=None, max_length=100)
    address: str | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    contact_email: EmailStr | None = None
    logo_path: str | None = Field(default=None, max_length=500)


class SocietyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    registration_no: str | None = Field(default=None, max_length=100)
    address: str | None = None
    contact_phone: str | None = Field(default=None, max_length=20)
    contact_email: EmailStr | None = None
    logo_path: str | None = Field(default=None, max_length=500)


class SocietyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    society_id: UUID
    name: str
    registration_no: str | None
    address: str | None
    contact_phone: str | None
    contact_email: str | None
    logo_path: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class SocietyListResponse(BaseModel):
    items: list[SocietyResponse]
    total: int
    limit: int
    offset: int