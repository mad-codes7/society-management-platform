from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


class AuditRepository:
    def list_logs(
        self,
        db: Session,
        *,
        society_id: Optional[UUID],
        action: Optional[str],
        limit: int,
        offset: int,
    ) -> tuple[list[AuditLog], int]:
        query = select(AuditLog)
        if society_id is not None:
            query = query.where(AuditLog.society_id == society_id)
        if action is not None:
            query = query.where(AuditLog.action == action)

        total = db.scalar(
            select(func.count()).select_from(query.subquery())
        ) or 0
        logs = list(
            db.scalars(
                query.order_by(AuditLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        return logs, total