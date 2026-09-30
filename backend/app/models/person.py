from __future__ import annotations
import uuid
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sqla_relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    first_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    last_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        unique=True,
        index=True,
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        index=True,
    )

    gender: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    dob: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    blood_group: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
    )

    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    user: Mapped[Optional["User"]] = sqla_relationship(
        "User",
        back_populates="person",
        uselist=False,
    )

    residents: Mapped[List[Resident]] = sqla_relationship(
        "Resident",
        back_populates="person",
        cascade="all, delete-orphan",
    )


class Resident(Base, TimestampMixin):
    __tablename__ = "residents"

    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.society_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.unit_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.person_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    resident_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="OWNER",
    )

    occupancy_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )

    move_in_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    move_out_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    is_primary_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    person: Mapped[Person] = sqla_relationship(
        "Person",
        back_populates="residents",
    )

    family_members: Mapped[List[FamilyMember]] = sqla_relationship(
        "FamilyMember",
        back_populates="resident",
        cascade="all, delete-orphan",
    )

    emergency_contacts: Mapped[List[EmergencyContact]] = sqla_relationship(
        "EmergencyContact",
        back_populates="resident",
        cascade="all, delete-orphan",
    )


class FamilyMember(Base, TimestampMixin):
    __tablename__ = "family_members"

    family_member_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.resident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.person_id", ondelete="SET NULL"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    gender: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    is_dependent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    resident: Mapped[Resident] = sqla_relationship(
        "Resident",
        back_populates="family_members",
    )


class EmergencyContact(Base, TimestampMixin):
    __tablename__ = "emergency_contacts"

    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.resident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    resident: Mapped[Resident] = sqla_relationship(
        "Resident",
        back_populates="emergency_contacts",
    )
