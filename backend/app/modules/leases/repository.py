from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.history import Lease
from app.models.person import Person, Resident
from app.models.property import Unit


class LeaseRepository:
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

    def has_overlapping_lease(
        self,
        db: Session,
        society_id: UUID,
        unit_id: UUID,
        lease_start: date,
        lease_end: Optional[date],
        exclude_lease_id: Optional[UUID] = None,
    ) -> bool:
        statement = select(Lease.lease_id).where(
            Lease.society_id == society_id,
            Lease.unit_id == unit_id,
            Lease.lease_start <= (lease_end or date.max),
            (Lease.lease_end.is_(None) | (Lease.lease_end >= lease_start)),
        )
        if exclude_lease_id is not None:
            statement = statement.where(Lease.lease_id != exclude_lease_id)
        return db.scalar(statement.limit(1)) is not None

    def create(self, db: Session, lease: Lease) -> Lease:
        db.add(lease)
        db.flush()
        return lease

    def get(
        self,
        db: Session,
        society_id: UUID,
        lease_id: UUID,
    ) -> Optional[Lease]:
        return db.scalar(
            select(Lease).where(
                Lease.society_id == society_id,
                Lease.lease_id == lease_id,
            )
        )

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        tenant_person_id: Optional[UUID],
    ) -> list[Lease]:
        statement = select(Lease).where(Lease.society_id == society_id)
        if unit_id is not None:
            statement = statement.where(Lease.unit_id == unit_id)
        if tenant_person_id is not None:
            statement = statement.where(Lease.tenant_person_id == tenant_person_id)
        return list(
            db.scalars(
                statement.order_by(Lease.lease_start.desc(), Lease.lease_id)
            )
        )
