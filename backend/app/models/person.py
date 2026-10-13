from __future__ import annotations
import uuid
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, ForeignKey, ForeignKeyConstraint, Index, SmallInteger, String, UniqueConstraint
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

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
        index=True,
    )

    mobile: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        index=True,
    )

    gender: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    date_of_birth: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    profile_photo_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)

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
    __table_args__ = (
        UniqueConstraint("society_id", "resident_id", name="uq_residents_society_id"),
        ForeignKeyConstraint(["society_id", "unit_id"], ["units.society_id", "units.unit_id"], ondelete="CASCADE"),
    )

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
        String(30),
        nullable=False,
        default="OWNER",
    )

    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)

    person: Mapped[Person] = sqla_relationship(
        "Person",
        back_populates="residents",
    )

    family_members: Mapped[List[FamilyMember]] = sqla_relationship(
        "FamilyMember",
        back_populates="resident",
        cascade="all, delete-orphan",
        foreign_keys="[FamilyMember.resident_id]",
    )

    emergency_contacts: Mapped[List[EmergencyContact]] = sqla_relationship(
        "EmergencyContact",
        back_populates="resident",
        cascade="all, delete-orphan",
    )


class FamilyMember(Base, TimestampMixin):
    __tablename__ = "family_members"
    __table_args__ = (
        Index("ix_family_members_society_id", "society_id"),
        ForeignKeyConstraint(["society_id", "resident_id"], ["residents.society_id", "residents.resident_id"], ondelete="CASCADE"),
    )
    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False
    )


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
        index=True,
    )

    relationship: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    emergency_contact: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    app_access_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)

    resident: Mapped[Resident] = sqla_relationship(
        "Resident",
        back_populates="family_members",
        foreign_keys="[FamilyMember.resident_id]",
    )


class EmergencyContact(Base, TimestampMixin):
    __tablename__ = "emergency_contacts"
    __table_args__ = (
        Index("ix_emergency_contacts_society_id", "society_id"),
        ForeignKeyConstraint(["society_id", "resident_id"], ["residents.society_id", "residents.resident_id"], ondelete="CASCADE"),
    )

    emergency_contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False
    )

    resident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("residents.resident_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    relationship: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    mobile: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    priority: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)

    resident: Mapped[Resident] = sqla_relationship(
        "Resident",
        back_populates="emergency_contacts",
    )
