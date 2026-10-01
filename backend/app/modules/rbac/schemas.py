from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)


class RoleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: UUID
    name: str
    description: Optional[str]
    is_active: bool


class PermissionCreate(BaseModel):
    code: str = Field(min_length=3, max_length=120)
    description: Optional[str] = Field(default=None, max_length=255)
    module: Optional[str] = Field(default=None, max_length=80)


class PermissionUpdate(BaseModel):
    description: Optional[str] = Field(default=None, max_length=255)
    module: Optional[str] = Field(default=None, max_length=80)


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permission_id: UUID
    code: str
    description: Optional[str]
    module: Optional[str]