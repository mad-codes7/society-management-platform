from __future__ import annotations
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.history import OccupancyHistory
from app.models.person import EmergencyContact, FamilyMember, Person, Resident
from app.modules.property.repository import PropertyRepository
from app.modules.residents.repository import ResidentRepository
from app.modules.residents.schemas import (
    EmergencyContactCreate,
    FamilyMemberCreate,
    ResidentCreate,
)


class ResidentService:

    def __init__(self):
        self.repository = ResidentRepository()
        self.property_repository = PropertyRepository()

    def create_resident(self, db: Session, data: ResidentCreate) -> Resident:
        unit = self.property_repository.get_unit_by_id(db, data.unit_id)
        if not unit or unit.society_id != data.society_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unit does not exist or does not belong to the specified society.",
            )

        person_by_email = self.repository.get_person_by_email(db, data.person.email) if data.person.email else None
        person_by_phone = self.repository.get_person_by_phone(db, data.person.phone) if data.person.phone else None

        if person_by_email and person_by_phone and person_by_email.person_id != person_by_phone.person_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provided email and phone number belong to different existing persons.",
            )

        person = person_by_email or person_by_phone

        if not person:
            person = Person(
                full_name=f"{data.person.first_name} {data.person.last_name}",
                email=data.person.email,
                mobile=data.person.phone,
                gender=data.person.gender,
                date_of_birth=data.person.dob,
                profile_photo_path=data.person.avatar_url,
            )
            person = self.repository.create_person(db, person)
        else:
            # Update missing/new fields on existing person if provided
            if data.person.email and not person.email:
                person.email = data.person.email
            if data.person.phone and not person.mobile:
                person.mobile = data.person.phone
            if data.person.avatar_url:
                person.profile_photo_path = data.person.avatar_url
            if data.person.gender:
                person.gender = data.person.gender
            if data.person.dob:
                person.date_of_birth = data.person.dob

        resident = Resident(
            society_id=data.society_id,
            unit_id=data.unit_id,
            person_id=person.person_id,
            resident_type=data.resident_type,
            status=data.occupancy_status,
            is_primary=data.is_primary_contact,
        )

        resident = self.repository.create_resident(db, resident)
        if data.move_in_date is not None:
            db.add(
                OccupancyHistory(
                    society_id=data.society_id,
                    unit_id=data.unit_id,
                    person_id=person.person_id,
                    occupancy_type=data.resident_type,
                    move_in_date=data.move_in_date,
                    status=data.occupancy_status,
                )
            )
        db.commit()
        db.refresh(resident)
        return resident

    def get_resident(self, db: Session, resident_id: UUID) -> Resident:
        resident = self.repository.get_resident_by_id(db, resident_id)
        if not resident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resident not found.",
            )
        return resident

    def list_residents(self, db: Session, society_id: UUID, unit_id: Optional[UUID] = None) -> List[Resident]:
        return self.repository.list_residents_by_society(db, society_id, unit_id)

    def add_family_member(self, db: Session, data: FamilyMemberCreate) -> FamilyMember:
        resident = self.get_resident(db, data.resident_id)

        if any((data.name, data.phone, data.gender)) or data.is_dependent is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="name, phone, gender and is_dependent are legacy fields without V2 destinations; use person_id, emergency_contact and app_access_enabled.",
            )

        if data.person_id:
            person = self.repository.get_person_by_id(db, data.person_id)
            if not person:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Specified person does not exist.",
                )

        family_member = FamilyMember(
            society_id=resident.society_id,
            resident_id=resident.resident_id,
            person_id=data.person_id,
            relationship=data.relationship,
            emergency_contact=data.emergency_contact,
            app_access_enabled=data.app_access_enabled,
        )
        family_member = self.repository.create_family_member(db, family_member)
        db.commit()
        db.refresh(family_member)
        return family_member

    def list_family_members(self, db: Session, resident_id: UUID) -> List[FamilyMember]:
        return self.repository.list_family_members(db, resident_id)

    def add_emergency_contact(self, db: Session, data: EmergencyContactCreate) -> EmergencyContact:
        resident = self.get_resident(db, data.resident_id)
        if data.person_id and not self.repository.get_person_by_id(db, data.person_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified person does not exist.",
            )
        contact = EmergencyContact(
            society_id=resident.society_id,
            resident_id=resident.resident_id,
            person_id=data.person_id,
            name=data.name,
            relationship=data.relationship,
            mobile=data.mobile or data.phone,
            priority=data.priority,
        )
        contact = self.repository.create_emergency_contact(db, contact)
        db.commit()
        db.refresh(contact)
        return contact

    def list_emergency_contacts(self, db: Session, resident_id: UUID) -> List[EmergencyContact]:
        return self.repository.list_emergency_contacts(db, resident_id)
