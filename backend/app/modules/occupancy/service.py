from __future__ import annotations

import re
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.history import OccupancyHistory
from app.modules.audit.service import audit_service
from app.modules.occupancy.repository import OccupancyRepository
from app.modules.occupancy.schemas import OccupancyCheckIn


class OccupancyService:
    def __init__(self, repository: Optional[OccupancyRepository] = None) -> None:
        self.repository = repository or OccupancyRepository()

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
    def _is_occupancy_exclusion_violation(error: IntegrityError) -> bool:
        diagnostic = getattr(error.orig, "diag", None)
        return (
            getattr(diagnostic, "constraint_name", None)
            == "ex_occupancy_history_active_person_unit_dates"
        )

    def check_in(
        self,
        db: Session,
        society_id: UUID,
        data: OccupancyCheckIn,
        actor_user_id: UUID,
    ) -> OccupancyHistory:
        move_in_date = self._parse_date(data.move_in_date, "move_in_date")
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
        if self.repository.has_overlapping_record(
            db, society_id, data.unit_id, data.person_id, move_in_date
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Occupancy dates overlap an existing record for this person and unit.",
            )

        occupancy = OccupancyHistory(
            society_id=society_id,
            unit_id=data.unit_id,
            person_id=data.person_id,
            occupancy_type=data.occupancy_type,
            move_in_date=move_in_date,
            status="ACTIVE",
        )
        try:
            occupancy = self.repository.create(db, occupancy)
            audit_service.record(
                db,
                action="occupancy_checked_in",
                entity_type="occupancy_history",
                entity_id=occupancy.occupancy_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                after_data={
                    "occupancy_type": occupancy.occupancy_type,
                    "move_in_date": occupancy.move_in_date.isoformat(),
                },
            )
            db.commit()
            db.refresh(occupancy)
            return occupancy
        except IntegrityError as error:
            db.rollback()
            if self._is_occupancy_exclusion_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Occupancy dates overlap an existing record for this person and unit.",
                ) from None
            raise

    def check_out(
        self,
        db: Session,
        society_id: UUID,
        occupancy_id: UUID,
        move_out_date_value: str,
        actor_user_id: UUID,
    ) -> OccupancyHistory:
        move_out_date = self._parse_date(move_out_date_value, "move_out_date")
        occupancy = self.repository.get(db, society_id, occupancy_id)
        if occupancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Occupancy record not found in this society.",
            )
        if occupancy.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Occupancy record is already inactive.",
            )
        if move_out_date < occupancy.move_in_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="move_out_date cannot be before move_in_date.",
            )

        before = {
            "status": occupancy.status,
            "move_out_date": (
                occupancy.move_out_date.isoformat()
                if occupancy.move_out_date is not None
                else None
            ),
        }
        occupancy.move_out_date = move_out_date
        occupancy.status = "INACTIVE"
        try:
            db.flush()
            audit_service.record(
                db,
                action="occupancy_checked_out",
                entity_type="occupancy_history",
                entity_id=occupancy.occupancy_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=before,
                after_data={
                    "status": occupancy.status,
                    "move_out_date": occupancy.move_out_date.isoformat(),
                },
            )
            db.commit()
            db.refresh(occupancy)
            return occupancy
        except IntegrityError:
            db.rollback()
            raise

    def get(
        self,
        db: Session,
        society_id: UUID,
        occupancy_id: UUID,
    ) -> OccupancyHistory:
        occupancy = self.repository.get(db, society_id, occupancy_id)
        if occupancy is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Occupancy record not found in this society.",
            )
        return occupancy

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        person_id: Optional[UUID],
    ) -> list[OccupancyHistory]:
        return self.repository.list(db, society_id, unit_id, person_id)


occupancy_service = OccupancyService()
