from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.core.security import MIN_PASSWORD_LENGTH


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=150)
    password: SecretStr = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(gt=0)


class MembershipSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    society_id: UUID
    status: str = Field(max_length=20)


class CurrentUserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: EmailStr
    person_id: UUID | None
    is_super_admin: bool
    is_active: bool
    memberships: list[MembershipSummary] = Field(default_factory=list)


class SocietyAdminCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr = Field(max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    gender: str | None = Field(default=None, max_length=20)
    dob: date | None = None
    initial_password: SecretStr = Field(min_length=MIN_PASSWORD_LENGTH)


class SocietyAdminPersonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    person_id: UUID
    first_name: str
    last_name: str
    email: EmailStr | None
    phone: str | None
    gender: str | None
    dob: date | None


class SocietyAdminCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: EmailStr
    is_active: bool
    is_super_admin: bool
    person: SocietyAdminPersonResponse


class SocietyMembershipCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    society_id: UUID


class SocietyMembershipCreateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: UUID
    user_id: UUID
    society_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
