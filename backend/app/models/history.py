from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, ForeignKeyConstraint, Numeric, String, UniqueConstraint, and_, func, literal_column, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Ownership(Base, TimestampMixin):
    __tablename__ = "ownerships"
    __table_args__ = (
        ForeignKeyConstraint(["society_id", "unit_id"], ["units.society_id", "units.unit_id"], ondelete="RESTRICT"),
        CheckConstraint("share_percentage IS NULL OR share_percentage BETWEEN 0 AND 100", name="ck_ownerships_share_percentage"),
        CheckConstraint("end_date IS NULL OR end_date > start_date", name="ck_ownerships_valid_dates"),
    )

    ownership_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.unit_id", ondelete="RESTRICT"), nullable=False, index=True)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="RESTRICT"), nullable=False, index=True)
    ownership_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    share_percentage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)


class Lease(Base, TimestampMixin):
    __tablename__ = "leases"
    __table_args__ = (
        ForeignKeyConstraint(["society_id", "unit_id"], ["units.society_id", "units.unit_id"], ondelete="RESTRICT"),
        ExcludeConstraint(
            ("society_id", "="),
            ("unit_id", "="),
            ("tenant_person_id", "="),
            (
                func.daterange(
                    literal_column("lease_start", type_=Date()),
                    func.coalesce(literal_column("lease_end", type_=Date()), text("'infinity'::date")),
                    "[]",
                ),
                "&&",
            ),
            where=and_(text("status = 'ACTIVE'")),
            name="ex_leases_active_tenant_unit_dates",
            using="gist",
        ),
        CheckConstraint("lease_end IS NULL OR lease_end > lease_start", name="ck_leases_valid_dates"),
    )

    lease_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.unit_id", ondelete="RESTRICT"), nullable=False, index=True)
    tenant_person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="RESTRICT"), nullable=False, index=True)
    owner_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="SET NULL"), nullable=True, index=True)
    lease_start: Mapped[date] = mapped_column(Date, nullable=False)
    lease_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)


class OccupancyHistory(Base, TimestampMixin):
    __tablename__ = "occupancy_history"
    __table_args__ = (
        ForeignKeyConstraint(["society_id", "unit_id"], ["units.society_id", "units.unit_id"], ondelete="RESTRICT"),
        ExcludeConstraint(
            ("society_id", "="),
            ("unit_id", "="),
            ("person_id", "="),
            (
                func.daterange(
                    literal_column("move_in_date", type_=Date()),
                    func.coalesce(
                        literal_column("move_out_date", type_=Date()),
                        text("'infinity'::date"),
                    ),
                    "[]",
                ),
                "&&",
            ),
            where=and_(text("status = 'ACTIVE'")),
            name="ex_occupancy_history_active_person_unit_dates",
            using="gist",
        ),
        CheckConstraint("move_out_date IS NULL OR move_out_date > move_in_date", name="ck_occupancy_history_valid_dates"),
    )

    occupancy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.unit_id", ondelete="RESTRICT"), nullable=False, index=True)
    person_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="RESTRICT"), nullable=False, index=True)
    occupancy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    move_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    move_out_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("society_id", "registration_number", name="uq_vehicles_society_registration"),
        ForeignKeyConstraint(["society_id", "unit_id"], ["units.society_id", "units.unit_id"], ondelete="CASCADE"),
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    society_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True)
    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.person_id", ondelete="SET NULL"), nullable=True, index=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    registration_number: Mapped[str] = mapped_column(String(30), nullable=False)
    vehicle_type: Mapped[str] = mapped_column(String(30), nullable=False)
    make_model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    colour: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)