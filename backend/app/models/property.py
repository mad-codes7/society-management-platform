from __future__ import annotations
import uuid
from typing import Optional, List

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Building(Base, TimestampMixin):
    __tablename__ = "buildings"

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

    code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    building_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="TOWER",
    )

    total_floors: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    floors: Mapped[List[Floor]] = relationship(
        "Floor",
        back_populates="building",
        cascade="all, delete-orphan",
    )

    units: Mapped[List[Unit]] = relationship(
        "Unit",
        back_populates="building",
        cascade="all, delete-orphan",
    )


class Floor(Base, TimestampMixin):
    __tablename__ = "floors"

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

    floor_name: Mapped[Optional[str]] = mapped_column(
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
    )


class UnitType(Base, TimestampMixin):
    __tablename__ = "unit_types"

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
        String(100),
        nullable=False,
    )

    super_builtup_area: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    carpet_area: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    units: Mapped[List[Unit]] = relationship(
        "Unit",
        back_populates="unit_type",
    )


class Unit(Base, TimestampMixin):
    __tablename__ = "units"

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
        String(20),
        nullable=False,
    )

    occupancy_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="VACANT",
    )

    is_commercial: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    building: Mapped[Building] = relationship(
        "Building",
        back_populates="units",
    )

    floor: Mapped[Floor] = relationship(
        "Floor",
        back_populates="units",
    )

    unit_type: Mapped[Optional[UnitType]] = relationship(
        "UnitType",
        back_populates="units",
    )
