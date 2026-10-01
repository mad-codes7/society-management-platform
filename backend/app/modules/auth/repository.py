from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import normalize_email
from app.models.person import Person
from app.models.user import SocietyMembership, User


class AuthRepository:
    def get_user_by_email(self, db: Session, email: str) -> Optional[User]:
        statement = select(User).where(func.lower(User.email) == normalize_email(email))
        return db.scalar(statement)

    def get_user_by_id(self, db: Session, user_id: UUID) -> Optional[User]:
        return db.get(User, user_id)

    def get_membership_by_id(
        self, db: Session, membership_id: UUID
    ) -> Optional[SocietyMembership]:
        return db.get(SocietyMembership, membership_id)

    def get_memberships_for_user(
        self, db: Session, user_id: UUID
    ) -> list[SocietyMembership]:
        statement = select(SocietyMembership).where(
            SocietyMembership.user_id == user_id
        )
        return list(db.scalars(statement).all())

    def get_person_by_email(self, db: Session, email: str) -> Optional[Person]:
        statement = select(Person).where(func.lower(Person.email) == normalize_email(email))
        return db.scalar(statement)

    def get_person_by_phone(self, db: Session, phone: str) -> Optional[Person]:
        statement = select(Person).where(Person.phone == phone)
        return db.scalar(statement)

    def create_person(self, db: Session, person: Person) -> Person:
        db.add(person)
        db.flush()
        return person

    def create_user(self, db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    def get_membership_for_user_in_society(
        self,
        db: Session,
        user_id: UUID,
        society_id: UUID,
    ) -> Optional[SocietyMembership]:
        statement = select(SocietyMembership).where(
            SocietyMembership.user_id == user_id,
            SocietyMembership.society_id == society_id,
        )
        return db.scalar(statement)

    def create_membership(
        self,
        db: Session,
        membership: SocietyMembership,
    ) -> SocietyMembership:
        db.add(membership)
        db.flush()
        return membership

    def get_active_memberships_for_user(
        self,
        db: Session,
        user_id: UUID,
    ) -> list[SocietyMembership]:
        statement = (
            select(SocietyMembership)
            .where(
                SocietyMembership.user_id == user_id,
                SocietyMembership.status == "ACTIVE",
            )
            .order_by(SocietyMembership.created_at)
        )
        return list(db.scalars(statement).all())

    def get_active_membership_for_user_in_society(
        self,
        db: Session,
        user_id: UUID,
        society_id: UUID,
    ) -> Optional[SocietyMembership]:
        statement = select(SocietyMembership).where(
            SocietyMembership.user_id == user_id,
            SocietyMembership.society_id == society_id,
            SocietyMembership.status == "ACTIVE",
        )
        return db.scalar(statement)

    def update_last_login_at(self, db: Session, user: User) -> User:
        user.last_login_at = datetime.now(timezone.utc)
        db.flush()
        return user
