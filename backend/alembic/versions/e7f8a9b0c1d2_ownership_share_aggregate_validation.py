"""enforce aggregate ownership shares under concurrent writes

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    for constraint_name, table_name in (
        ("ck_occupancy_history_valid_dates", "occupancy_history"),
        ("ck_leases_valid_dates", "leases"),
        ("ck_ownerships_valid_dates", "ownerships"),
    ):
        op.drop_constraint(constraint_name, table_name, type_="check")
    op.create_check_constraint(
        "ck_occupancy_history_valid_dates", "occupancy_history",
        "move_out_date IS NULL OR move_out_date >= move_in_date",
    )
    op.create_check_constraint(
        "ck_leases_valid_dates", "leases", "lease_end IS NULL OR lease_end >= lease_start",
    )
    op.create_check_constraint(
        "ck_ownerships_valid_dates", "ownerships", "end_date IS NULL OR end_date >= start_date",
    )
    violations = connection.execute(sa.text("""
        SELECT count(*) FROM (
            SELECT DISTINCT a.unit_id, a.start_date
            FROM ownerships a
            WHERE a.status = 'ACTIVE' AND a.share_percentage IS NOT NULL
              AND (SELECT sum(b.share_percentage)
                   FROM ownerships b
                   WHERE b.unit_id = a.unit_id AND b.status = 'ACTIVE'
                     AND b.share_percentage IS NOT NULL
                     AND b.start_date <= a.start_date
                     AND (b.end_date IS NULL OR b.end_date >= a.start_date)) > 100
        ) violating_periods
    """)).scalar_one()
    if violations:
        raise RuntimeError(
            "Cannot enforce aggregate ownership shares: existing active ownership "
            f"data exceeds 100% on {violations} unit/date points. Resolve the conflicts and retry."
        )

    # One transaction-scoped advisory lock gives every ownership writer the
    # same lock order, including multi-row unit moves, and avoids deadlocks.
    op.execute("""
        CREATE FUNCTION serialize_ownership_changes_before_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            PERFORM pg_advisory_xact_lock(1836016742);
            IF TG_OP = 'DELETE' THEN
                RETURN OLD;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE FUNCTION validate_ownership_unit_share_totals() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            unit_to_check uuid;
        BEGIN
            FOR unit_to_check IN
                SELECT DISTINCT candidate
                FROM unnest(ARRAY[
                    CASE WHEN TG_OP <> 'INSERT' THEN OLD.unit_id END,
                    CASE WHEN TG_OP <> 'DELETE' THEN NEW.unit_id END
                ]) AS candidate
                WHERE candidate IS NOT NULL
                ORDER BY candidate
            LOOP
                IF EXISTS (
                    SELECT 1
                    FROM ownerships pivot
                    WHERE pivot.unit_id = unit_to_check
                      AND pivot.status = 'ACTIVE'
                      AND pivot.share_percentage IS NOT NULL
                      AND (
                          SELECT sum(active.share_percentage)
                          FROM ownerships active
                          WHERE active.unit_id = unit_to_check
                            AND active.status = 'ACTIVE'
                            AND active.share_percentage IS NOT NULL
                            AND active.start_date <= pivot.start_date
                            AND (active.end_date IS NULL OR active.end_date >= pivot.start_date)
                      ) > 100
                ) THEN
                    RAISE EXCEPTION USING
                        ERRCODE = '23514',
                        CONSTRAINT = 'ck_ownerships_active_unit_share_total',
                        MESSAGE = format(
                            'active ownership shares for unit %s exceed 100%% on an overlapping date',
                            unit_to_check
                        );
                END IF;
            END LOOP;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER ownerships_serialize_writes
        BEFORE INSERT OR UPDATE OR DELETE ON ownerships
        FOR EACH ROW EXECUTE FUNCTION serialize_ownership_changes_before_mutation()
    """)
    op.execute("""
        CREATE TRIGGER ownerships_validate_share_totals
        AFTER INSERT OR UPDATE OR DELETE ON ownerships
        FOR EACH ROW EXECUTE FUNCTION validate_ownership_unit_share_totals()
    """)


def downgrade() -> None:
    raise RuntimeError(
        "Cannot downgrade aggregate ownership validation safely. Restore a verified "
        "pre-migration backup instead; no downgrade operations were run."
    )
