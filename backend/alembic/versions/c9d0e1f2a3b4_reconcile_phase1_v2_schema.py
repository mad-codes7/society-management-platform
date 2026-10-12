"""reconcile applied Phase 1 V2 schema with approved design

Revision ID: c9d0e1f2a3b4
Revises: b7c8d9e0f1a2
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, Sequence[str], None] = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def _require_no_rows(predicate: str, message: str) -> None:
    count = op.get_bind().execute(sa.text(f"SELECT count(*) FROM unit_types WHERE {predicate}")).scalar_one()
    if count:
        raise RuntimeError(f"Cannot reconcile Phase 1 V2 schema: {message} ({count} rows).")


def upgrade() -> None:
    # V2 allows gender values up to 30 characters; widening preserves all data.
    op.alter_column(
        "persons",
        "gender",
        existing_type=sa.String(20),
        type_=sa.String(30),
        existing_nullable=True,
    )

    # V2 defines unit type names as VARCHAR(50). Do not truncate existing values.
    _require_no_rows(
        "length(name) > 50",
        "unit_types.name contains values longer than VARCHAR(50); shorten them before retrying",
    )
    op.alter_column(
        "unit_types",
        "name",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=False,
    )

    op.alter_column(
        "emergency_contacts",
        "name",
        existing_type=sa.String(150),
        nullable=True,
    )
    op.alter_column(
        "emergency_contacts",
        "relationship",
        existing_type=sa.String(50),
        nullable=True,
    )

    op.execute("CREATE INDEX IF NOT EXISTS ix_emergency_contacts_society_id ON emergency_contacts (society_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_family_members_society_id ON family_members (society_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_family_members_status ON family_members (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_leases_owner_person_id ON leases (owner_person_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_residents_status ON residents (status)")

    op.create_foreign_key(
        "family_members_society_id_fkey",
        "family_members",
        "societies",
        ["society_id"],
        ["society_id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    connection = op.get_bind()
    null_count = connection.execute(sa.text(
        "SELECT count(*) FROM emergency_contacts WHERE name IS NULL OR relationship IS NULL"
    )).scalar_one()
    if null_count:
        raise RuntimeError(
            "Cannot downgrade schema reconciliation: emergency contact NULL values would violate the previous schema."
        )
    long_gender_count = connection.execute(sa.text(
        "SELECT count(*) FROM persons WHERE length(gender) > 20"
    )).scalar_one()
    if long_gender_count:
        raise RuntimeError(
            "Cannot downgrade schema reconciliation: persons.gender contains values longer than VARCHAR(20)."
        )

    op.drop_constraint("family_members_society_id_fkey", "family_members", type_="foreignkey")
    op.drop_index("ix_residents_status", table_name="residents")
    op.drop_index("ix_leases_owner_person_id", table_name="leases")
    op.drop_index("ix_family_members_status", table_name="family_members")
    op.drop_index("ix_family_members_society_id", table_name="family_members")
    op.drop_index("ix_emergency_contacts_society_id", table_name="emergency_contacts")
    op.alter_column("emergency_contacts", "relationship", nullable=False)
    op.alter_column("emergency_contacts", "name", nullable=False)
    op.alter_column(
        "unit_types",
        "name",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=False,
    )
    op.alter_column(
        "persons",
        "gender",
        existing_type=sa.String(30),
        type_=sa.String(20),
        existing_nullable=True,
    )
