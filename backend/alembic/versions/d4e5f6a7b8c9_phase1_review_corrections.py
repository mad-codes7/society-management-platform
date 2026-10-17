"""apply Phase 1 review corrections

Revision ID: d4e5f6a7b8c9
Revises: c9d0e1f2a3b4
"""

import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def _require_no_rows(sql: str, message: str) -> None:
    count = op.get_bind().execute(sa.text(sql)).scalar_one()
    if count:
        raise RuntimeError(f"Cannot apply Phase 1 review corrections: {message} ({count} rows).")


def _backfill_role_codes() -> None:
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT role_id, name FROM roles ORDER BY role_id")).mappings().all()
    codes: dict[str, object] = {}
    for row in rows:
        code = re.sub(r"[^a-z0-9]+", "_", row["name"].lower()).strip("_")
        if not code:
            raise RuntimeError(f"Cannot derive roles.code from role {row['role_id']}; resolve its name first.")
        if code in codes:
            raise RuntimeError(
                f"Cannot derive unique roles.code for roles {codes[code]} and {row['role_id']}; resolve the names first."
            )
        codes[code] = row["role_id"]
        connection.execute(
            sa.text("UPDATE roles SET code = :code WHERE role_id = :role_id"),
            {"code": code, "role_id": row["role_id"]},
        )


def upgrade() -> None:
    op.add_column("roles", sa.Column("code", sa.String(length=80), nullable=True))
    _backfill_role_codes()
    op.alter_column("roles", "code", nullable=False)
    op.create_unique_constraint("uq_roles_code", "roles", ["code"])

    op.add_column(
        "user_roles",
        sa.Column("valid_from", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
    )
    op.add_column("user_roles", sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True))
    op.add_column("user_roles", sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=True))
    op.execute("UPDATE user_roles SET valid_from = COALESCE(valid_from, created_at, now()), status = COALESCE(status, 'ACTIVE')")
    op.alter_column("user_roles", "valid_from", nullable=False)
    op.alter_column("user_roles", "status", nullable=False)
    op.create_index("ix_user_roles_status", "user_roles", ["status"])
    op.create_check_constraint(
        "ck_user_roles_valid_dates",
        "user_roles",
        "valid_to IS NULL OR valid_to > valid_from",
    )

    op.alter_column(
        "society_settings",
        "late_fee_rule",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="late_fee_rule::jsonb",
    )
    op.alter_column(
        "society_settings",
        "gate_timing",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="gate_timing::jsonb",
    )
    op.alter_column(
        "society_settings",
        "visitor_policy",
        existing_type=sa.JSON(),
        type_=postgresql.JSONB(),
        postgresql_using="visitor_policy::jsonb",
    )
    op.alter_column(
        "society_settings",
        "grace_period_days",
        existing_type=sa.Integer(),
        type_=sa.SmallInteger(),
    )
    op.alter_column(
        "society_settings",
        "due_day",
        existing_type=sa.Integer(),
        type_=sa.SmallInteger(),
    )
    op.add_column("society_settings", sa.Column("emergency_config", postgresql.JSONB(), nullable=True))

    op.execute("ALTER TABLE units DROP CONSTRAINT units_society_unit_type_fkey")
    op.create_foreign_key(
        "units_society_unit_type_fkey",
        "units",
        "unit_types",
        ["society_id", "unit_type_id"],
        ["society_id", "unit_type_id"],
        ondelete="SET NULL (unit_type_id)",
    )

    op.execute("ALTER TABLE occupancy_history DROP CONSTRAINT ex_occupancy_history_active_unit_dates")
    _require_no_rows(
        """
        SELECT count(*) FROM occupancy_history a
        JOIN occupancy_history b
          ON a.occupancy_id < b.occupancy_id
         AND a.society_id = b.society_id
         AND a.unit_id = b.unit_id
         AND a.person_id = b.person_id
         AND a.status = 'ACTIVE' AND b.status = 'ACTIVE'
         AND daterange(a.move_in_date, COALESCE(a.move_out_date, 'infinity'::date), '[]')
             && daterange(b.move_in_date, COALESCE(b.move_out_date, 'infinity'::date), '[]')
        """,
        "overlapping active occupancy records exist for the same person and unit",
    )
    op.execute(
        """
        ALTER TABLE occupancy_history ADD CONSTRAINT ex_occupancy_history_active_person_unit_dates
        EXCLUDE USING gist (
            society_id WITH =,
            unit_id WITH =,
            person_id WITH =,
            daterange(move_in_date, COALESCE(move_out_date, 'infinity'::date), '[]') WITH &&
        ) WHERE (status = 'ACTIVE')
        """
    )
    op.create_check_constraint(
        "ck_occupancy_history_valid_dates",
        "occupancy_history",
        "move_out_date IS NULL OR move_out_date > move_in_date",
    )

    _require_no_rows(
        """
        SELECT count(*) FROM leases a
        JOIN leases b
          ON a.lease_id < b.lease_id
         AND a.society_id = b.society_id
         AND a.unit_id = b.unit_id
         AND a.status = 'ACTIVE' AND b.status = 'ACTIVE'
         AND daterange(a.lease_start, COALESCE(a.lease_end, 'infinity'::date), '[]')
             && daterange(b.lease_start, COALESCE(b.lease_end, 'infinity'::date), '[]')
        """,
        "overlapping active leases exist for the same unit",
    )
    op.execute(
        """
        ALTER TABLE leases ADD CONSTRAINT ex_leases_active_unit_dates
        EXCLUDE USING gist (
            society_id WITH =,
            unit_id WITH =,
            daterange(lease_start, COALESCE(lease_end, 'infinity'::date), '[]') WITH &&
        ) WHERE (status = 'ACTIVE')
        """
    )
    op.create_check_constraint("ck_leases_valid_dates", "leases", "lease_end IS NULL OR lease_end > lease_start")

    op.create_check_constraint(
        "ck_ownerships_share_percentage",
        "ownerships",
        "share_percentage IS NULL OR share_percentage BETWEEN 0 AND 100",
    )
    op.create_check_constraint("ck_ownerships_valid_dates", "ownerships", "end_date IS NULL OR end_date > start_date")
    op.create_check_constraint(
        "ck_society_memberships_valid_dates",
        "society_memberships",
        "left_at IS NULL OR left_at >= joined_at",
    )


def downgrade() -> None:
    op.drop_constraint("ck_society_memberships_valid_dates", "society_memberships", type_="check")
    op.drop_constraint("ck_ownerships_valid_dates", "ownerships", type_="check")
    op.drop_constraint("ck_ownerships_share_percentage", "ownerships", type_="check")
    op.drop_constraint("ck_leases_valid_dates", "leases", type_="check")
    op.execute("ALTER TABLE leases DROP CONSTRAINT ex_leases_active_unit_dates")
    op.drop_constraint("ck_occupancy_history_valid_dates", "occupancy_history", type_="check")
    op.execute("ALTER TABLE occupancy_history DROP CONSTRAINT ex_occupancy_history_active_person_unit_dates")
    op.execute(
        """
        ALTER TABLE occupancy_history ADD CONSTRAINT ex_occupancy_history_active_unit_dates
        EXCLUDE USING gist (
            unit_id WITH =,
            daterange(move_in_date, COALESCE(move_out_date, 'infinity'::date), '[]') WITH &&
        ) WHERE (status = 'ACTIVE')
        """
    )
    op.drop_constraint("units_society_unit_type_fkey", "units", type_="foreignkey")
    op.create_foreign_key(
        "units_society_unit_type_fkey", "units", "unit_types",
        ["society_id", "unit_type_id"], ["society_id", "unit_type_id"], ondelete="SET NULL"
    )
    op.drop_column("society_settings", "emergency_config")
    op.alter_column("society_settings", "due_day", existing_type=sa.SmallInteger(), type_=sa.Integer())
    op.alter_column("society_settings", "grace_period_days", existing_type=sa.SmallInteger(), type_=sa.Integer())
    for column in ("visitor_policy", "gate_timing", "late_fee_rule"):
        op.alter_column(
            "society_settings", column, existing_type=postgresql.JSONB(), type_=sa.JSON(), postgresql_using=f"{column}::json"
        )
    op.drop_constraint("ck_user_roles_valid_dates", "user_roles", type_="check")
    op.drop_index("ix_user_roles_status", table_name="user_roles")
    op.drop_column("user_roles", "status")
    op.drop_column("user_roles", "valid_to")
    op.drop_column("user_roles", "valid_from")
    op.drop_constraint("uq_roles_code", "roles", type_="unique")
    op.drop_column("roles", "code")
