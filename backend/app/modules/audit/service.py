from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.modules.audit.repository import AuditRepository


class AuditService:
    def __init__(self, repository: AuditRepository | None = None) -> None:
        self.repository = repository or AuditRepository()

    def record(
        self,
        db: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        actor_user_id: Optional[UUID] = None,
        society_id: Optional[UUID] = None,
        before_data: Optional[dict] = None,
        after_data: Optional[dict] = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            society_id=society_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            before_data=before_data,
            after_data=after_data,
        )
        db.add(entry)
        db.flush()
        return entry

    def list_logs(
        self,
        db: Session,
        *,
        society_id: UUID | None,
        action: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[AuditLog], int]:
        return self.repository.list_logs(
            db,
            society_id=society_id,
            action=action,
            limit=limit,
            offset=offset,
        )


audit_service = AuditService()