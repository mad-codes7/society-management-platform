"""create_society_core_tables

Revision ID: f8a92b34c56d
Revises: e6a3bf25fe43
Create Date: 2026-09-25 22:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f8a92b34c56d"
down_revision: Union[str, Sequence[str], None] = "e6a3bf25fe43"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. society_settings
    op.create_table(
        "society_settings",
        sa.Column("setting_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("financial_year_start", sa.Date(), nullable=True),
        sa.Column("billing_cycle", sa.String(20), nullable=True, server_default="MONTHLY"),
        sa.Column("late_fee_rule", sa.JSON(), nullable=True),
        sa.Column("grace_period_days", sa.Integer(), nullable=True, server_default="7"),
        sa.Column("due_day", sa.Integer(), nullable=True, server_default="10"),
        sa.Column("gate_timing", sa.JSON(), nullable=True),
        sa.Column("visitor_policy", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 2. buildings
    op.create_table(
        "buildings",
        sa.Column("building_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("building_type", sa.String(20), nullable=False, server_default="TOWER"),
        sa.Column("total_floors", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 3. floors
    op.create_table(
        "floors",
        sa.Column("floor_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("building_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("floor_number", sa.Integer(), nullable=False),
        sa.Column("floor_name", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 4. unit_types
    op.create_table(
        "unit_types",
        sa.Column("unit_type_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("super_builtup_area", sa.Float(), nullable=True),
        sa.Column("carpet_area", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 5. units
    op.create_table(
        "units",
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("building_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("buildings.building_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("floor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("floors.floor_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("unit_type_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("unit_types.unit_type_id", ondelete="SET NULL"), nullable=True),
        sa.Column("unit_number", sa.String(20), nullable=False),
        sa.Column("occupancy_status", sa.String(20), nullable=False, server_default="VACANT"),
        sa.Column("is_commercial", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 6. persons
    op.create_table(
        "persons",
        sa.Column("person_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(150), nullable=True, unique=True, index=True),
        sa.Column("phone", sa.String(20), nullable=True, unique=True, index=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("dob", sa.Date(), nullable=True),
        sa.Column("blood_group", sa.String(10), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 7. residents
    op.create_table(
        "residents",
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("societies.society_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("units.unit_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("persons.person_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("resident_type", sa.String(20), nullable=False, server_default="OWNER"),
        sa.Column("occupancy_status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("move_in_date", sa.Date(), nullable=True),
        sa.Column("move_out_date", sa.Date(), nullable=True),
        sa.Column("is_primary_contact", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 8. family_members
    op.create_table(
        "family_members",
        sa.Column("family_member_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("residents.resident_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("persons.person_id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("is_dependent", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 9. emergency_contacts
    op.create_table(
        "emergency_contacts",
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("resident_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("residents.resident_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("relationship", sa.String(50), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("emergency_contacts")
    op.drop_table("family_members")
    op.drop_table("residents")
    op.drop_table("persons")
    op.drop_table("units")
    op.drop_table("unit_types")
    op.drop_table("floors")
    op.drop_table("buildings")
    op.drop_table("society_settings")
