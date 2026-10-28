from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import OccupancyHistory
from app.models.person import Resident
from app.models.property import Unit


class OccupancyRepository:
    def get_unit(self, db: Session, society_id: UUID, unit_id: UUID) -> Optional[Unit]:
        return db.scalar(
            select(Unit).where(
                Unit.society_id == society_id,
                Unit.unit_id == unit_id,
            )
        )

    def person_belongs_to_society(
        self,
        db: Session,
        society_id: UUID,
        person_id: UUID,
    ) -> bool:
        return (
            db.scalar(
                select(Resident.resident_id)
                .where(
                    Resident.society_id == society_id,
                    Resident.person_id == person_id,
                )
                .limit(1)
            )
            is not None
        )

    def has_overlapping_record(
        self,
        db: Session,
        society_id: UUID,
        unit_id: UUID,
        person_id: UUID,
        move_in_date: date,
    ) -> bool:
        return (
            db.scalar(
                select(OccupancyHistory.occupancy_id)
                .where(
                    OccupancyHistory.society_id == society_id,
                    OccupancyHistory.unit_id == unit_id,
                    OccupancyHistory.person_id == person_id,
                    OccupancyHistory.status == "ACTIVE",
                    (
                        OccupancyHistory.move_out_date.is_(None)
                        | (OccupancyHistory.move_out_date >= move_in_date)
                    ),
                )
                .limit(1)
            )
            is not None
        )

    def create(self, db: Session, occupancy: OccupancyHistory) -> OccupancyHistory:
        db.add(occupancy)
        db.flush()
        return occupancy

    def get(
        self,
        db: Session,
        society_id: UUID,
        occupancy_id: UUID,
    ) -> Optional[OccupancyHistory]:
        return db.scalar(
            select(OccupancyHistory).where(
                OccupancyHistory.society_id == society_id,
                OccupancyHistory.occupancy_id == occupancy_id,
            )
        )

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        person_id: Optional[UUID],
    ) -> list[OccupancyHistory]:
        statement = select(OccupancyHistory).where(
            OccupancyHistory.society_id == society_id
        )
        if unit_id is not None:
            statement = statement.where(OccupancyHistory.unit_id == unit_id)
        if person_id is not None:
            statement = statement.where(OccupancyHistory.person_id == person_id)
        return list(
            db.scalars(
                statement.order_by(
                    OccupancyHistory.move_in_date.desc(),
                    OccupancyHistory.occupancy_id,
                )
            )
        )
