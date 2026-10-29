from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.history import Ownership
from app.modules.audit.service import audit_service
from app.modules.ownership.repository import OwnershipRepository
from app.modules.ownership.schemas import (
    OwnershipCreate,
    OwnershipTransfer,
    OwnershipUpdate,
)

SHARE_CONFLICT_MESSAGE = (
    "Active ownership shares for a unit cannot exceed 100% on overlapping dates."
)


class OwnershipService:
    def __init__(self, repository: Optional[OwnershipRepository] = None) -> None:
        self.repository = repository or OwnershipRepository()

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a valid ISO date (YYYY-MM-DD).",
            )
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a valid ISO date (YYYY-MM-DD).",
            ) from None

    @staticmethod
    def _status_for_end_date(end_date: Optional[date]) -> str:
        return "ACTIVE" if end_date is None or end_date >= date.today() else "INACTIVE"

    @staticmethod
    def _audit_data(ownership: Ownership) -> dict[str, object]:
        return {
            "ownership_type": ownership.ownership_type,
            "share_percentage": (
                str(ownership.share_percentage)
                if ownership.share_percentage is not None
                else None
            ),
            "start_date": ownership.start_date.isoformat(),
            "end_date": ownership.end_date.isoformat() if ownership.end_date else None,
            "status": ownership.status,
        }

    @staticmethod
    def _is_share_violation(error: IntegrityError) -> bool:
        diagnostic = getattr(error.orig, "diag", None)
        constraint_name = getattr(diagnostic, "constraint_name", None)
        sqlstate = getattr(error.orig, "sqlstate", None) or getattr(
            error.orig, "pgcode", None
        )
        return (
            constraint_name
            in {
                "ck_ownerships_active_unit_share_total",
                "ownerships_validate_share_totals",
            }
            and sqlstate in (None, "23514")
        )

    def _commit_with_share_validation(
        self,
        db: Session,
        records: list[Ownership],
    ) -> None:
        db.flush()
        db.execute(text("SET CONSTRAINTS ownerships_validate_share_totals IMMEDIATE"))
        db.commit()
        for record in records:
            db.refresh(record)

    def create(
        self,
        db: Session,
        society_id: UUID,
        data: OwnershipCreate,
        actor_user_id: UUID,
    ) -> Ownership:
        start_date = self._parse_date(data.start_date, "start_date")
        end_date = (
            self._parse_date(data.end_date, "end_date")
            if data.end_date is not None
            else None
        )
        if end_date is not None and end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date cannot be before start_date.",
            )
        if self.repository.get_unit(db, society_id, data.unit_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unit not found in this society.",
            )
        if not self.repository.person_belongs_to_society(
            db, society_id, data.person_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found in this society.",
            )

        ownership = Ownership(
            society_id=society_id,
            unit_id=data.unit_id,
            person_id=data.person_id,
            ownership_type=data.ownership_type,
            share_percentage=data.share_percentage,
            start_date=start_date,
            end_date=end_date,
            status=self._status_for_end_date(end_date),
        )
        try:
            ownership = self.repository.create(db, ownership)
            audit_service.record(
                db,
                action="ownership_created",
                entity_type="ownership",
                entity_id=ownership.ownership_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                after_data=self._audit_data(ownership),
            )
            self._commit_with_share_validation(db, [ownership])
            return ownership
        except IntegrityError as error:
            db.rollback()
            if self._is_share_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=SHARE_CONFLICT_MESSAGE,
                ) from None
            raise

    def update(
        self,
        db: Session,
        society_id: UUID,
        ownership_id: UUID,
        data: OwnershipUpdate,
        actor_user_id: UUID,
    ) -> Ownership:
        ownership = self.repository.get(db, society_id, ownership_id)
        if ownership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ownership record not found in this society.",
            )

        changes = data.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one ownership field must be provided.",
            )
        if "end_date" in changes:
            if changes["end_date"] is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date cannot be cleared; ownership history is immutable.",
                )
            end_date = self._parse_date(changes["end_date"], "end_date")
            if end_date < ownership.start_date:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="end_date cannot be before start_date.",
                )
        else:
            end_date = ownership.end_date

        before = self._audit_data(ownership)
        if "ownership_type" in changes:
            ownership.ownership_type = changes["ownership_type"]
        if "share_percentage" in changes:
            ownership.share_percentage = changes["share_percentage"]
        if "end_date" in changes:
            ownership.end_date = end_date
            ownership.status = self._status_for_end_date(end_date)
        after = self._audit_data(ownership)

        try:
            audit_service.record(
                db,
                action="ownership_updated",
                entity_type="ownership",
                entity_id=ownership.ownership_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=before,
                after_data=after,
            )
            self._commit_with_share_validation(db, [ownership])
            return ownership
        except IntegrityError as error:
            db.rollback()
            if self._is_share_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=SHARE_CONFLICT_MESSAGE,
                ) from None
            raise

    def transfer(
        self,
        db: Session,
        society_id: UUID,
        ownership_id: UUID,
        data: OwnershipTransfer,
        actor_user_id: UUID,
    ) -> tuple[Ownership, Ownership]:
        source = self.repository.get(db, society_id, ownership_id)
        if source is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ownership record not found in this society.",
            )
        if source.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only active ownership records can be transferred.",
            )
        transfer_date = self._parse_date(data.transfer_date, "transfer_date")
        if transfer_date <= source.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="transfer_date must be after the ownership start_date.",
            )
        if data.receiving_person_id == source.person_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The receiving person must differ from the current owner.",
            )
        if not self.repository.person_belongs_to_society(
            db, society_id, data.receiving_person_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Receiving person not found in this society.",
            )

        source_before = self._audit_data(source)
        source.end_date = transfer_date - timedelta(days=1)
        source.status = self._status_for_end_date(source.end_date)
        receiving = Ownership(
            society_id=society_id,
            unit_id=source.unit_id,
            person_id=data.receiving_person_id,
            ownership_type=source.ownership_type,
            share_percentage=source.share_percentage,
            start_date=transfer_date,
            status="ACTIVE",
        )
        try:
            db.add(receiving)
            db.flush()
            source_after = self._audit_data(source)
            audit_service.record(
                db,
                action="ownership_transferred_out",
                entity_type="ownership",
                entity_id=source.ownership_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=source_before,
                after_data=source_after,
            )
            audit_service.record(
                db,
                action="ownership_transferred_in",
                entity_type="ownership",
                entity_id=receiving.ownership_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                after_data=self._audit_data(receiving),
            )
            self._commit_with_share_validation(db, [source, receiving])
            return source, receiving
        except IntegrityError as error:
            db.rollback()
            if self._is_share_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=SHARE_CONFLICT_MESSAGE,
                ) from None
            raise

    def get(
        self,
        db: Session,
        society_id: UUID,
        ownership_id: UUID,
    ) -> Ownership:
        ownership = self.repository.get(db, society_id, ownership_id)
        if ownership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ownership record not found in this society.",
            )
        return ownership

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        person_id: Optional[UUID],
    ) -> list[Ownership]:
        return self.repository.list(db, society_id, unit_id, person_id)


ownership_service = OwnershipService()
