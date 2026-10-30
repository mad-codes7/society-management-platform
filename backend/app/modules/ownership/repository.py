from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.models.history import Ownership
from app.models.person import FamilyMember, Person, Resident
from app.models.property import Unit
from app.models.user import SocietyMembership, User


class OwnershipRepository:
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

        resident_exists = exists(
            select(Resident.resident_id).where(
                Resident.society_id == society_id,
                Resident.person_id == person_id,
            )
        )
        family_member_exists = exists(
            select(FamilyMember.family_member_id)
            .join(Resident, Resident.resident_id == FamilyMember.resident_id)
            .where(
                Resident.society_id == society_id,
                FamilyMember.person_id == person_id,
            )
        )
        membership_exists = exists(
            select(SocietyMembership.membership_id)
            .join(User, User.user_id == SocietyMembership.user_id)
            .where(
                SocietyMembership.society_id == society_id,
                User.person_id == person_id,
            )
        )
        prior_ownership_exists = exists(
            select(Ownership.ownership_id).where(
                Ownership.society_id == society_id,
                Ownership.person_id == person_id,
            )
        )
        return bool(
            db.scalar(
                select(
                    resident_exists
                    | family_member_exists
                    | membership_exists
                    | prior_ownership_exists
                )
            )
        )

    def create(self, db: Session, ownership: Ownership) -> Ownership:
        db.add(ownership)
        db.flush()
        return ownership

    def get(
        self,
        db: Session,
        society_id: UUID,
        ownership_id: UUID,
    ) -> Optional[Ownership]:
        return db.scalar(
            select(Ownership).where(
                Ownership.society_id == society_id,
                Ownership.ownership_id == ownership_id,
            )
        )

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        person_id: Optional[UUID],
    ) -> list[Ownership]:
        statement = select(Ownership).where(Ownership.society_id == society_id)
        if unit_id is not None:
            statement = statement.where(Ownership.unit_id == unit_id)
        if person_id is not None:
            statement = statement.where(Ownership.person_id == person_id)
        return list(
            db.scalars(
                statement.order_by(
                    Ownership.start_date.desc(),
                    Ownership.ownership_id,
                )
            )
        )
