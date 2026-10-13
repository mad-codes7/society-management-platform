from __future__ import annotations
import uuid
from typing import Optional, List

from sqlalchemy import Boolean, ForeignKey, ForeignKeyConstraint, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Building(Base, TimestampMixin):
    __tablename__ = "buildings"
    __table_args__ = (
        UniqueConstraint("society_id", "code", name="uq_buildings_society_code"),
        UniqueConstraint("society_id", "building_id", name="uq_buildings_society_id"),
    )

    building_id: Mapped[uuid.UUID] = mapped_column(
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

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    code: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    building_type: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    total_floors: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)

    floors: Mapped[List[Floor]] = relationship(
        "Floor",
        back_populates="building",
        cascade="all, delete-orphan",
    )

    units: Mapped[List[Unit]] = relationship(
        "Unit",
        back_populates="building",
        cascade="all, delete-orphan",
        foreign_keys="Unit.building_id",
    )


class Floor(Base, TimestampMixin):
    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint("building_id", "floor_number", name="uq_floors_building_number"),
        UniqueConstraint("building_id", "floor_id", name="uq_floors_building_id"),
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.building_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    floor_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    name: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    building: Mapped[Building] = relationship(
        "Building",
        back_populates="floors",
    )

    units: Mapped[List[Unit]] = relationship(
        "Unit",
        back_populates="floor",
        cascade="all, delete-orphan",
        foreign_keys="Unit.floor_id",
    )


class UnitType(Base, TimestampMixin):
    __tablename__ = "unit_types"
    __table_args__ = (
        UniqueConstraint("society_id", "name", name="uq_unit_types_society_name"),
        UniqueConstraint("society_id", "unit_type_id", name="uq_unit_types_society_id"),
    )

    unit_type_id: Mapped[uuid.UUID] = mapped_column(
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

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    default_area: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    area_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    units: Mapped[List[Unit]] = relationship(
        "Unit",
        back_populates="unit_type",
        foreign_keys="Unit.unit_type_id",
    )


class Unit(Base, TimestampMixin):
    __tablename__ = "units"
    __table_args__ = (
        UniqueConstraint("society_id", "building_id", "unit_number", name="uq_units_society_building_number"),
        UniqueConstraint("society_id", "unit_id", name="uq_units_society_id"),
        ForeignKeyConstraint(["society_id", "building_id"], ["buildings.society_id", "buildings.building_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["building_id", "floor_id"], ["floors.building_id", "floors.floor_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["society_id", "unit_type_id"], ["unit_types.society_id", "unit_types.unit_type_id"], ondelete="SET NULL"),
    )

    unit_id: Mapped[uuid.UUID] = mapped_column(
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

    building_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("buildings.building_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("floors.floor_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    unit_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("unit_types.unit_type_id", ondelete="SET NULL"),
        nullable=True,
    )

    unit_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    area: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

    occupancy_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="VACANT",
    )

    building: Mapped[Building] = relationship(
        "Building",
        back_populates="units",
        foreign_keys="Unit.building_id",
    )

    floor: Mapped[Floor] = relationship(
        "Floor",
        back_populates="units",
        foreign_keys="Unit.floor_id",
    )

    unit_type: Mapped[Optional[UnitType]] = relationship(
        "UnitType",
        back_populates="units",
        foreign_keys="Unit.unit_type_id",
    )