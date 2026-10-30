from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import Vehicle
from app.models.person import Person, Resident
from app.models.property import Unit


class VehicleRepository:
    def get_unit(
        self,
        db: Session,
        society_id: UUID,
        unit_id: UUID,
    ) -> Optional[Unit]:
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
        if db.get(Person, person_id) is None:
            return False
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

    def has_active_resident_association(
        self,
        db: Session,
        society_id: UUID,
        unit_id: UUID,
        person_id: UUID,
    ) -> bool:
        return (
            db.scalar(
                select(Resident.resident_id)
                .where(
                    Resident.society_id == society_id,
                    Resident.unit_id == unit_id,
                    Resident.person_id == person_id,
                    Resident.status == "ACTIVE",
                )
                .limit(1)
            )
            is not None
        )

    def create(self, db: Session, vehicle: Vehicle) -> Vehicle:
        db.add(vehicle)
        db.flush()
        return vehicle

    def get(
        self,
        db: Session,
        society_id: UUID,
        vehicle_id: UUID,
    ) -> Optional[Vehicle]:
        return db.scalar(
            select(Vehicle).where(
                Vehicle.society_id == society_id,
                Vehicle.vehicle_id == vehicle_id,
            )
        )

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        person_id: Optional[UUID],
        vehicle_status: Optional[str],
    ) -> list[Vehicle]:
        statement = select(Vehicle).where(Vehicle.society_id == society_id)
        if unit_id is not None:
            statement = statement.where(Vehicle.unit_id == unit_id)
        if person_id is not None:
            statement = statement.where(Vehicle.person_id == person_id)
        if vehicle_status is not None:
            statement = statement.where(Vehicle.status == vehicle_status)
        return list(
            db.scalars(
                statement.order_by(Vehicle.registration_number, Vehicle.vehicle_id)
            )
        )
