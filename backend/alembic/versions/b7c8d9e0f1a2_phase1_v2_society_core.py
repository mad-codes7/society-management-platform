"""implement approved Phase 1 V2 society core schema

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def _require_no_values(table: str, column: str, predicate: str, message: str) -> None:
    connection = op.get_bind()
    count = connection.execute(
        sa.text(f"SELECT count(*) FROM {table} WHERE {predicate}")
    ).scalar_one()
    if count:
        raise RuntimeError(f"Cannot apply Phase 1 V2 migration: {message} ({count} rows).")


def _rename(table: str, old: str, new: str) -> None:
    op.alter_column(table, old, new_column_name=new)


def _occupancy_history_parameters(resident_rows):
    for row in resident_rows:
        yield {
            "occupancy_id": uuid.uuid4(),
            "society_id": row["society_id"],
            "unit_id": row["unit_id"],
            "person_id": row["person_id"],
            "occupancy_type": row["resident_type"],
            "move_in_date": row["move_in_date"],
            "move_out_date": row["move_out_date"],
            "status": row["occupancy_status"],
        }


def _backfill_user_person_links() -> None:
    connection = op.get_bind()
    unlinked_users = connection.execute(sa.text(
        "SELECT user_id, email FROM users WHERE person_id IS NULL ORDER BY user_id"
    )).mappings().all()

    for user in unlinked_users:
        email = user["email"]
        if not email or not email.strip():
            raise RuntimeError(
                f"Cannot map user {user['user_id']} to persons: the account email is empty."
            )

        matches = connection.execute(
            sa.text(
                "SELECT person_id FROM persons "
                "WHERE email IS NOT NULL AND lower(email) = lower(:email)"
            ),
            {"email": email},
        ).scalars().all()
        if len(matches) > 1:
            raise RuntimeError(
                f"Cannot map user {user['user_id']} ({email}) to persons: "
                f"{len(matches)} persons match the account email. Resolve the duplicate identities first."
            )

        if matches:
            person_id = matches[0]
            occupied_by = connection.execute(
                sa.text(
                    "SELECT user_id FROM users "
                    "WHERE person_id = :person_id AND user_id <> :user_id"
                ),
                {"person_id": person_id, "user_id": user["user_id"]},
            ).scalars().all()
            if occupied_by:
                raise RuntimeError(
                    f"Cannot map user {user['user_id']} ({email}) to person {person_id}: "
                    f"that person is already linked to user {occupied_by[0]}."
                )
        else:
            person_id = uuid.uuid4()
            connection.execute(
                sa.text(
                    "INSERT INTO persons (person_id, full_name, email, status) "
                    "VALUES (:person_id, :full_name, :email, 'ACTIVE')"
                ),
                {
                    "person_id": person_id,
                    # The account email is the only verified identity value available here.
                    "full_name": email.strip(),
                    "email": email,
                },
            )

        connection.execute(
            sa.text("UPDATE users SET person_id = :person_id WHERE user_id = :user_id"),
            {"person_id": person_id, "user_id": user["user_id"]},
        )


def upgrade() -> None:
    # Identity conversion. full_name is deliberately derived only from existing values.
    op.add_column("persons", sa.Column("full_name", sa.String(150), nullable=True))
    op.get_bind().execute(
        sa.text("UPDATE persons SET full_name = trim(concat_ws(' ', first_name, last_name))")
    )
    _require_no_values(
        "persons", "full_name", "full_name IS NULL OR btrim(full_name) = ''",
        "persons.full_name cannot be populated from first_name/last_name",
    )
    op.alter_column("persons", "full_name", nullable=False)
    _rename("persons", "phone", "mobile")
    _rename("persons", "dob", "date_of_birth")
    _rename("persons", "avatar_url", "profile_photo_path")
    _require_no_values(
        "persons", "blood_group", "blood_group IS NOT NULL",
        "persons.blood_group has no V2 destination; export or clear it before retrying",
    )
    op.drop_column("persons", "blood_group")
    for index_name in ("ix_persons_email", "ix_persons_phone"):
        op.execute(sa.text(f"DROP INDEX IF EXISTS {index_name}"))
    op.add_column("persons", sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False))
    op.drop_column("persons", "first_name")
    op.drop_column("persons", "last_name")
    op.create_index("ix_persons_email", "persons", ["email"])
    op.create_index("ix_persons_mobile", "persons", ["mobile"])
    op.create_index("ix_persons_status", "persons", ["status"])

    # Authentication accounts must now identify a person. Existing accounts are linked by
    # exact normalized email or receive a person containing only the account email.
    _backfill_user_person_links()
    _require_no_values(
        "users", "person_id", "person_id IS NULL",
        "users.person_id could not be linked to a person",
    )
    op.drop_constraint("users_person_id_fkey", "users", type_="foreignkey")
    op.create_foreign_key("users_person_id_fkey", "users", "persons", ["person_id"], ["person_id"], ondelete="RESTRICT")
    op.alter_column("users", "person_id", nullable=False)

    op.add_column("society_memberships", sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True))
    op.add_column("society_memberships", sa.Column("left_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("society_memberships", "joined_at", nullable=False)

    # Property master alignment.
    op.add_column("buildings", sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False))
    op.create_index("ix_buildings_status", "buildings", ["status"])
    op.alter_column("buildings", "code", type_=sa.String(30), nullable=True)
    op.alter_column("buildings", "building_type", type_=sa.String(30), nullable=True)
    op.alter_column("buildings", "total_floors", nullable=True)
    _rename("floors", "floor_name", "name")
    op.add_column("unit_types", sa.Column("description", sa.String(200), nullable=True))
    op.add_column("unit_types", sa.Column("default_area", sa.Numeric(12, 2), nullable=True))
    op.add_column("unit_types", sa.Column("area_unit", sa.String(20), nullable=True))
    op.add_column("unit_types", sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.get_bind().execute(sa.text("UPDATE unit_types SET default_area = super_builtup_area WHERE default_area IS NULL"))
    _require_no_values(
        "unit_types", "carpet_area", "carpet_area IS NOT NULL",
        "unit_types.carpet_area has no V2 destination; export or clear it before retrying",
    )
    op.drop_column("unit_types", "super_builtup_area")
    op.drop_column("unit_types", "carpet_area")
    op.add_column("units", sa.Column("area", sa.Numeric(12, 2), nullable=True))
    _require_no_values(
        "units", "is_commercial", "is_commercial IS TRUE",
        "units.is_commercial has no V2 destination; export or clear it before retrying",
    )
    op.drop_column("units", "is_commercial")
    op.alter_column("units", "unit_number", type_=sa.String(30))
    op.alter_column("residents", "resident_type", type_=sa.String(30))
    op.alter_column("users", "password_hash", nullable=True)

    # Convert current resident movement into immutable occupancy history before removing it.
    connection = op.get_bind()
    extension_available = connection.execute(sa.text(
        "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'btree_gist')"
    )).scalar_one()
    if not extension_available:
        raise RuntimeError(
            "Cannot apply Phase 1 V2 migration: PostgreSQL extension btree_gist is unavailable; "
            "install it before enabling occupancy overlap protection."
        )
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public")

    op.create_table(
        "occupancy_history",
        sa.Column("occupancy_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("occupancy_type", sa.String(20), nullable=False),
        sa.Column("move_in_date", sa.Date(), nullable=False),
        sa.Column("move_out_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["society_id"], ["societies.society_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.unit_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="RESTRICT"),
    )
    # Do not install the legacy unit-only exclusion here: it rejects valid
    # concurrent household members while resident rows are being copied.
    # The review correction installs the person-and-unit exclusion after its
    # pre-validation, which also supports databases that applied this revision.
    _require_no_values(
        "residents", "move_in_date", "move_in_date IS NULL",
        "resident movement history cannot be preserved without move_in_date; supply dates before retrying",
    )
    resident_rows = connection.execute(sa.text(
        "SELECT society_id, unit_id, person_id, resident_type, move_in_date, move_out_date, occupancy_status "
        "FROM residents"
    )).mappings().all()
    occupancy_insert = sa.text(
        "INSERT INTO occupancy_history "
        "(occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, move_out_date, status) "
        "VALUES (:occupancy_id, :society_id, :unit_id, :person_id, :occupancy_type, :move_in_date, :move_out_date, :status)"
    )
    for parameters in _occupancy_history_parameters(resident_rows):
        connection.execute(occupancy_insert, parameters)
    op.add_column("residents", sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=True))
    op.add_column("residents", sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=True))
    op.get_bind().execute(sa.text("UPDATE residents SET status = occupancy_status, is_primary = is_primary_contact"))
    op.alter_column("residents", "status", nullable=False)
    op.alter_column("residents", "is_primary", nullable=False)
    op.drop_column("residents", "occupancy_status")
    op.drop_column("residents", "move_in_date")
    op.drop_column("residents", "move_out_date")
    op.drop_column("residents", "is_primary_contact")

    # Family members retain only relationship flags; duplicated contact data cannot be discarded.
    op.add_column("family_members", sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.get_bind().execute(sa.text("UPDATE family_members f SET society_id = r.society_id FROM residents r WHERE r.resident_id = f.resident_id"))
    _require_no_values("family_members", "society_id", "society_id IS NULL", "family member society could not be derived from resident")
    op.alter_column("family_members", "society_id", nullable=False)
    _require_no_values("family_members", "name", "name IS NOT NULL", "family_members.name has no V2 destination")
    _require_no_values("family_members", "phone", "phone IS NOT NULL", "family_members.phone has no V2 destination")
    _require_no_values("family_members", "gender", "gender IS NOT NULL", "family_members.gender has no V2 destination")
    _require_no_values("family_members", "is_dependent", "is_dependent IS TRUE", "family_members.is_dependent has no V2 destination")
    op.add_column("family_members", sa.Column("emergency_contact", sa.Boolean(), nullable=True))
    op.add_column("family_members", sa.Column("app_access_enabled", sa.Boolean(), nullable=True))
    op.add_column("family_members", sa.Column("status", sa.String(20), nullable=True))
    op.execute(sa.text("UPDATE family_members SET emergency_contact = false, app_access_enabled = false, status = 'ACTIVE'"))
    op.alter_column("family_members", "emergency_contact", nullable=False)
    op.alter_column("family_members", "app_access_enabled", nullable=False)
    op.alter_column("family_members", "status", nullable=False)
    op.drop_column("family_members", "name")
    op.drop_column("family_members", "phone")
    op.drop_column("family_members", "gender")
    op.drop_column("family_members", "is_dependent")
    op.create_index("ix_family_members_person_id", "family_members", ["person_id"])

    _rename("emergency_contacts", "contact_id", "emergency_contact_id")
    op.add_column("emergency_contacts", sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("emergency_contacts", sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("emergency_contacts", sa.Column("mobile", sa.String(20), nullable=True))
    op.add_column("emergency_contacts", sa.Column("priority", sa.SmallInteger(), nullable=True))
    op.get_bind().execute(sa.text("UPDATE emergency_contacts e SET society_id = r.society_id, mobile = e.phone FROM residents r WHERE r.resident_id = e.resident_id"))
    _require_no_values("emergency_contacts", "society_id", "society_id IS NULL", "emergency contact society could not be derived from resident")
    _require_no_values("emergency_contacts", "is_primary", "is_primary IS TRUE", "emergency_contacts.is_primary has no V2 destination")
    op.alter_column("emergency_contacts", "society_id", nullable=False)
    op.drop_column("emergency_contacts", "phone")
    op.drop_column("emergency_contacts", "is_primary")
    op.create_foreign_key("emergency_contacts_person_id_fkey", "emergency_contacts", "persons", ["person_id"], ["person_id"], ondelete="SET NULL")
    op.create_foreign_key("emergency_contacts_society_id_fkey", "emergency_contacts", "societies", ["society_id"], ["society_id"], ondelete="CASCADE")
    op.create_index("ix_emergency_contacts_person_id", "emergency_contacts", ["person_id"])

    op.create_table(
        "ownerships",
        sa.Column("ownership_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ownership_type", sa.String(30), nullable=True),
        sa.Column("share_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["society_id"], ["societies.society_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.unit_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "leases",
        sa.Column("lease_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_person_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lease_start", sa.Date(), nullable=False),
        sa.Column("lease_end", sa.Date(), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["society_id"], ["societies.society_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.unit_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_person_id"], ["persons.person_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_person_id"], ["persons.person_id"], ondelete="SET NULL"),
    )
    op.create_table(
        "vehicles",
        sa.Column("vehicle_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("society_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("registration_number", sa.String(30), nullable=False),
        sa.Column("vehicle_type", sa.String(30), nullable=False),
        sa.Column("make_model", sa.String(100), nullable=True),
        sa.Column("colour", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["society_id"], ["societies.society_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["persons.person_id"], ondelete="SET NULL"),
        sa.UniqueConstraint("society_id", "registration_number", name="uq_vehicles_society_registration"),
    )
    for table, column in (("ownerships", "society_id"), ("ownerships", "unit_id"), ("ownerships", "person_id"), ("leases", "society_id"), ("leases", "unit_id"), ("leases", "tenant_person_id"), ("vehicles", "society_id"), ("vehicles", "person_id"), ("vehicles", "unit_id"), ("occupancy_history", "society_id"), ("occupancy_history", "unit_id"), ("occupancy_history", "person_id")):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index("ix_occupancy_history_status", "occupancy_history", ["status"])
    op.create_index("ix_ownerships_status", "ownerships", ["status"])
    op.create_index("ix_leases_status", "leases", ["status"])
    op.create_index("ix_vehicles_status", "vehicles", ["status"])

    op.create_unique_constraint("uq_floors_building_id", "floors", ["building_id", "floor_id"])
    _require_no_values(
        "floors", "floor_number",
        "(building_id, floor_number) IN (SELECT building_id, floor_number FROM floors GROUP BY building_id, floor_number HAVING count(*) > 1)",
        "duplicate floor numbers exist within a building",
    )
    _require_no_values(
        "unit_types", "name",
        "(society_id, name) IN (SELECT society_id, name FROM unit_types GROUP BY society_id, name HAVING count(*) > 1)",
        "duplicate unit type names exist within a society",
    )
    _require_no_values(
        "units", "unit_number",
        "(society_id, building_id, unit_number) IN (SELECT society_id, building_id, unit_number FROM units GROUP BY society_id, building_id, unit_number HAVING count(*) > 1)",
        "duplicate unit numbers exist within a building and society",
    )
    _require_no_values(
        "buildings", "code",
        "code IS NOT NULL AND (society_id, code) IN (SELECT society_id, code FROM buildings WHERE code IS NOT NULL GROUP BY society_id, code HAVING count(*) > 1)",
        "duplicate building codes exist within a society",
    )
    op.create_unique_constraint("uq_floors_building_number", "floors", ["building_id", "floor_number"])
    op.create_unique_constraint("uq_unit_types_society_name", "unit_types", ["society_id", "name"])
    op.create_unique_constraint("uq_unit_types_society_id", "unit_types", ["society_id", "unit_type_id"])
    op.create_unique_constraint("uq_units_society_building_number", "units", ["society_id", "building_id", "unit_number"])
    op.create_unique_constraint("uq_units_society_id", "units", ["society_id", "unit_id"])
    op.create_unique_constraint("uq_buildings_society_code", "buildings", ["society_id", "code"])
    op.create_unique_constraint("uq_buildings_society_id", "buildings", ["society_id", "building_id"])
    op.create_unique_constraint("uq_residents_society_id", "residents", ["society_id", "resident_id"])

    op.create_foreign_key(
        "units_society_building_fkey", "units", "buildings",
        ["society_id", "building_id"], ["society_id", "building_id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "units_building_floor_fkey", "units", "floors",
        ["building_id", "floor_id"], ["building_id", "floor_id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "units_society_unit_type_fkey", "units", "unit_types",
        ["society_id", "unit_type_id"], ["society_id", "unit_type_id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "vehicles_society_unit_fkey", "vehicles", "units",
        ["society_id", "unit_id"], ["society_id", "unit_id"], ondelete="CASCADE"
    )
    for table in ("occupancy_history", "ownerships", "leases"):
        op.create_foreign_key(
            f"{table}_society_unit_fkey", table, "units",
            ["society_id", "unit_id"], ["society_id", "unit_id"], ondelete="RESTRICT"
        )
    op.create_foreign_key(
        "residents_society_unit_fkey", "residents", "units",
        ["society_id", "unit_id"], ["society_id", "unit_id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "family_members_society_resident_fkey", "family_members", "residents",
        ["society_id", "resident_id"], ["society_id", "resident_id"], ondelete="CASCADE"
    )
    op.create_foreign_key(
        "emergency_contacts_society_resident_fkey", "emergency_contacts", "residents",
        ["society_id", "resident_id"], ["society_id", "resident_id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    raise RuntimeError("Phase 1 V2 downgrade is intentionally blocked: it would discard migrated ownership, lease, occupancy, vehicle, and identity data. Restore a pre-V2 backup instead.")
