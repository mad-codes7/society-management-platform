from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: UUID
    actor_user_id: Optional[UUID]
    society_id: Optional[UUID]
    action: str
    entity_type: str
    entity_id: Optional[str]
    before_data: Optional[dict[str, Any]]
    after_data: Optional[dict[str, Any]]
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int