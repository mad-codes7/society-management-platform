"""add users and society memberships

Revision ID: d2c9a63f1b74
Revises: f8a92b34c56d
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d2c9a63f1b74"
down_revision: Union[str, Sequence[str], None] = "f8a92b34c56d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.String(150), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_super_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_person_id", "users", ["person_id"], unique=True)

    op.create_table(
        "society_memberships",
        sa.Column("membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["society_id"], ["societies.society_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("membership_id"),
        sa.UniqueConstraint(
            "user_id",
            "society_id",
            name="uq_society_memberships_user_society",
        ),
    )
    op.create_index("ix_society_memberships_user_id", "society_memberships", ["user_id"], unique=False)
    op.create_index("ix_society_memberships_society_id", "society_memberships", ["society_id"], unique=False)
    op.create_index("ix_society_memberships_status", "society_memberships", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_society_memberships_status", table_name="society_memberships")
    op.drop_index("ix_society_memberships_society_id", table_name="society_memberships")
    op.drop_index("ix_society_memberships_user_id", table_name="society_memberships")
    op.drop_table("society_memberships")

    op.drop_index("ix_users_person_id", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
