from __future__ import annotations
from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Person Schemas
class PersonCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=20)
    gender: Optional[str] = Field(default=None, max_length=20)
    dob: Optional[date] = None
    blood_group: Optional[str] = Field(default=None, max_length=10)
    avatar_url: Optional[str] = Field(default=None, max_length=500)


class PersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: UUID
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    gender: Optional[str]
    dob: Optional[date]
    blood_group: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime
    updated_at: datetime


# Resident Schemas
class ResidentCreate(BaseModel):
    society_id: UUID
    unit_id: UUID
    person: PersonCreate
    resident_type: str = Field(default="OWNER", max_length=20)
    occupancy_status: str = Field(default="ACTIVE", max_length=20)
    move_in_date: Optional[date] = None
    is_primary_contact: bool = Field(default=False)


class ResidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    resident_id: UUID
    society_id: UUID
    unit_id: UUID
    person_id: UUID
    resident_type: str
    occupancy_status: str
    move_in_date: Optional[date]
    move_out_date: Optional[date]
    is_primary_contact: bool
    person: PersonResponse
    created_at: datetime
    updated_at: datetime


# FamilyMember Schemas
class FamilyMemberCreate(BaseModel):
    resident_id: UUID
    person_id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=150)
    relationship: str = Field(min_length=1, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    gender: Optional[str] = Field(default=None, max_length=20)
    is_dependent: bool = Field(default=True)


class FamilyMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    family_member_id: UUID
    resident_id: UUID
    person_id: Optional[UUID]
    name: str
    relationship: str
    phone: Optional[str]
    gender: Optional[str]
    is_dependent: bool
    created_at: datetime
    updated_at: datetime


# EmergencyContact Schemas
class EmergencyContactCreate(BaseModel):
    resident_id: UUID
    name: str = Field(min_length=1, max_length=150)
    relationship: str = Field(min_length=1, max_length=50)
    phone: str = Field(min_length=1, max_length=20)
    is_primary: bool = Field(default=False)


class EmergencyContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    contact_id: UUID
    resident_id: UUID
    name: str
    relationship: str
    phone: str
    is_primary: bool
    created_at: datetime
    updated_at: datetime
