from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sqla_relationship

from app.models.base import Base, TimestampMixin


class Society(Base, TimestampMixin):
    __tablename__ = "societies"

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
    )

    registration_no: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
    )

    address: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    contact_phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    contact_email: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    logo_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
        index=True,
    )

    settings: Mapped[Optional[SocietySetting]] = sqla_relationship(
        "SocietySetting",
        back_populates="society",
        uselist=False,
        cascade="all, delete-orphan",
    )


class SocietySetting(Base, TimestampMixin):
    __tablename__ = "society_settings"

    setting_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.society_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    financial_year_start: Mapped[Optional[datetime]] = mapped_column(
        Date,
        nullable=True,
    )

    billing_cycle: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        default="MONTHLY",
    )

    late_fee_rule: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    grace_period_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=7,
    )

    due_day: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=10,
    )

    gate_timing: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    visitor_policy: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    society: Mapped[Society] = sqla_relationship(
        "Society",
        back_populates="settings",
    )