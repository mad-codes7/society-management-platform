from __future__ import annotations
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.person import EmergencyContact, FamilyMember, Person, Resident


class ResidentRepository:

    # Person methods
    def get_person_by_email_or_phone(self, db: Session, email: Optional[str], phone: Optional[str]) -> Optional[Person]:
        if email:
            person = db.scalar(select(Person).where(Person.email == email))
            if person:
                return person
        if phone:
            person = db.scalar(select(Person).where(Person.phone == phone))
            if person:
                return person
        return None

    def create_person(self, db: Session, person: Person) -> Person:
        db.add(person)
        db.flush()
        db.refresh(person)
        return person

    # Resident methods
    def create_resident(self, db: Session, resident: Resident) -> Resident:
        db.add(resident)
        db.flush()
        db.refresh(resident)
        return resident

    def get_resident_by_id(self, db: Session, resident_id: UUID) -> Optional[Resident]:
        stmt = select(Resident).where(Resident.resident_id == resident_id).options(joinedload(Resident.person))
        return db.scalar(stmt)

    def list_residents_by_society(self, db: Session, society_id: UUID, unit_id: Optional[UUID] = None) -> List[Resident]:
        query = select(Resident).where(Resident.society_id == society_id).options(joinedload(Resident.person))
        if unit_id:
            query = query.where(Resident.unit_id == unit_id)
        return list(db.scalars(query.order_by(Resident.created_at.desc())).all())

    # FamilyMember methods
    def create_family_member(self, db: Session, family_member: FamilyMember) -> FamilyMember:
        db.add(family_member)
        db.flush()
        db.refresh(family_member)
        return family_member

    def list_family_members(self, db: Session, resident_id: UUID) -> List[FamilyMember]:
        stmt = select(FamilyMember).where(FamilyMember.resident_id == resident_id)
        return list(db.scalars(stmt).all())

    # EmergencyContact methods
    def create_emergency_contact(self, db: Session, contact: EmergencyContact) -> EmergencyContact:
        db.add(contact)
        db.flush()
        db.refresh(contact)
        return contact

    def list_emergency_contacts(self, db: Session, resident_id: UUID) -> List[EmergencyContact]:
        stmt = select(EmergencyContact).where(EmergencyContact.resident_id == resident_id)
        return list(db.scalars(stmt).all())
