from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship as sqla_relationship

from app.models.base import Base, TimestampMixin
from app.models.person import Person
from app.models.society import Society


class User(Base, TimestampMixin):
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.person_id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        unique=True,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    is_super_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    person: Mapped[Optional[Person]] = sqla_relationship(
        "Person",
        back_populates="user",
        uselist=False,
    )

    society_memberships: Mapped[List["SocietyMembership"]] = sqla_relationship(
        "SocietyMembership",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class SocietyMembership(Base, TimestampMixin):
    __tablename__ = "society_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "society_id",
            name="uq_society_memberships_user_society",
        ),
        Index("ix_society_memberships_user_id", "user_id"),
        Index("ix_society_memberships_society_id", "society_id"),
        Index("ix_society_memberships_status", "status"),
    )

    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )

    society_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("societies.society_id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )

    user: Mapped[User] = sqla_relationship(
        "User",
        back_populates="society_memberships",
    )

    society: Mapped[Society] = sqla_relationship(
        "Society",
        back_populates="memberships",
    )

    user_roles: Mapped[List["UserRole"]] = sqla_relationship(
        "UserRole",
        back_populates="membership",
        cascade="all, delete-orphan",
    )
