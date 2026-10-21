from app.models.base import Base
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateTable
from sqlalchemy import text
from uuid import uuid4


def _property_fixture(connection):
    society_id, building_id, floor_id, unit_id, unit_type_id = [uuid4() for _ in range(5)]
    person_a, person_b = uuid4(), uuid4()
    connection.execute(
        text("INSERT INTO societies (society_id, name, status) VALUES (:id, :name, 'ACTIVE')"),
        {"id": society_id, "name": f"Review Society {society_id}"},
    )
    connection.execute(
        text("INSERT INTO buildings (building_id, society_id, name, status) VALUES (:id, :society_id, 'Tower', 'ACTIVE')"),
        {"id": building_id, "society_id": society_id},
    )
    connection.execute(
        text("INSERT INTO floors (floor_id, building_id, floor_number) VALUES (:id, :building_id, 1)"),
        {"id": floor_id, "building_id": building_id},
    )
    connection.execute(
        text("INSERT INTO unit_types (unit_type_id, society_id, name, is_active) VALUES (:id, :society_id, 'Flat', true)"),
        {"id": unit_type_id, "society_id": society_id},
    )
    connection.execute(
        text("INSERT INTO units (unit_id, society_id, building_id, floor_id, unit_type_id, unit_number, occupancy_status) VALUES (:id, :society_id, :building_id, :floor_id, :unit_type_id, '101', 'OCCUPIED')"),
        {"id": unit_id, "society_id": society_id, "building_id": building_id, "floor_id": floor_id, "unit_type_id": unit_type_id},
    )
    for person_id, name in ((person_a, "Resident A"), (person_b, "Resident B")):
        connection.execute(
            text("INSERT INTO persons (person_id, full_name, status) VALUES (:id, :name, 'ACTIVE')"),
            {"id": person_id, "name": name},
        )
    return society_id, unit_id, unit_type_id, person_a, person_b


def test_phase1_v2_tables_and_columns_are_registered() -> None:
    expected = {
        "ownerships": {
            "ownership_id", "society_id", "unit_id", "person_id", "ownership_type",
            "share_percentage", "start_date", "end_date", "status", "created_at", "updated_at",
        },
        "leases": {
            "lease_id", "society_id", "unit_id", "tenant_person_id", "owner_person_id",
            "lease_start", "lease_end", "status", "created_at", "updated_at",
        },
        "occupancy_history": {
            "occupancy_id", "society_id", "unit_id", "person_id", "occupancy_type",
            "move_in_date", "move_out_date", "status", "created_at", "updated_at",
        },
        "vehicles": {
            "vehicle_id", "society_id", "person_id", "unit_id", "registration_number",
            "vehicle_type", "make_model", "colour", "status", "created_at", "updated_at",
        },
    }
    for table_name, columns in expected.items():
        assert table_name in Base.metadata.tables
        assert columns <= set(Base.metadata.tables[table_name].columns.keys())

    assert {"full_name", "mobile", "date_of_birth", "profile_photo_path", "status"} <= set(Base.metadata.tables["persons"].columns.keys())
    assert {"description", "default_area", "area_unit", "is_active"} <= set(Base.metadata.tables["unit_types"].columns.keys())
    assert {"status", "is_primary"} <= set(Base.metadata.tables["residents"].columns.keys())
    assert {"joined_at", "left_at"} <= set(Base.metadata.tables["society_memberships"].columns.keys())
    assert {"code"} <= set(Base.metadata.tables["roles"].columns.keys())
    assert {"valid_from", "valid_to", "status"} <= set(Base.metadata.tables["user_roles"].columns.keys())
    settings = Base.metadata.tables["society_settings"]
    assert str(settings.c.late_fee_rule.type) == "JSONB"
    assert str(settings.c.gate_timing.type) == "JSONB"
    assert str(settings.c.visitor_policy.type) == "JSONB"
    assert str(settings.c.emergency_config.type) == "JSONB"
    assert str(settings.c.grace_period_days.type) == "SMALLINT"
    assert str(settings.c.due_day.type) == "SMALLINT"
    assert {"status"} <= set(Base.metadata.tables["buildings"].columns.keys())
    assert Base.metadata.tables["buildings"].c.status.nullable is False
    assert Base.metadata.tables["residents"].c.resident_type.type.length == 30
    assert Base.metadata.tables["users"].c.password_hash.nullable is True
    assert Base.metadata.tables["family_members"].c.emergency_contact.default is None
    assert Base.metadata.tables["persons"].c.mobile.type.length == 20
    assert Base.metadata.tables["persons"].c.gender.type.length == 30
    assert Base.metadata.tables["unit_types"].c.name.type.length == 50


def test_phase1_v2_scoped_keys_are_declared() -> None:
    for table_name, constraint_name in (
        ("buildings", "uq_buildings_society_code"),
        ("floors", "uq_floors_building_number"),
        ("unit_types", "uq_unit_types_society_name"),
        ("units", "uq_units_society_building_number"),
        ("units", "uq_units_society_id"),
        ("vehicles", "uq_vehicles_society_registration"),
    ):
        constraints = {constraint.name for constraint in Base.metadata.tables[table_name].constraints}
        assert constraint_name in constraints

    unit_fk_columns = {
        tuple(foreign_key.column_keys)
        for foreign_key in Base.metadata.tables["units"].foreign_key_constraints
    }
    assert ("society_id", "building_id") in unit_fk_columns
    assert ("building_id", "floor_id") in unit_fk_columns
    assert ("society_id", "unit_type_id") in unit_fk_columns

    unit_key_constraints = {
        constraint.name for constraint in Base.metadata.tables["units"].constraints
    }
    assert "uq_units_society_id" in unit_key_constraints

    for table_name in ("ownerships", "leases", "occupancy_history", "vehicles"):
        composite_fks = {
            tuple(foreign_key.column_keys)
            for foreign_key in Base.metadata.tables[table_name].foreign_key_constraints
            if foreign_key.referred_table.name == "units"
        }
        assert ("society_id", "unit_id") in composite_fks

    vehicle_fk_columns = {
        tuple(foreign_key.column_keys)
        for foreign_key in Base.metadata.tables["vehicles"].foreign_key_constraints
    }
    assert ("society_id", "unit_id") in vehicle_fk_columns

    exclusion_names = {
        constraint.name
        for constraint in Base.metadata.tables["occupancy_history"].constraints
        if constraint.name
    }
    assert "ex_occupancy_history_active_person_unit_dates" in exclusion_names
    occupancy_ddl = str(
        CreateTable(Base.metadata.tables["occupancy_history"]).compile(
            dialect=postgresql.dialect()
        )
    )
    assert "daterange(move_in_date, coalesce(move_out_date" in occupancy_ddl
    assert "person_id" in occupancy_ddl
    assert "daterange('move_in_date'" not in occupancy_ddl
    assert "coalesce('move_out_date'" not in occupancy_ddl

    expected_indexes = {
        "ix_emergency_contacts_society_id": "emergency_contacts",
        "ix_family_members_society_id": "family_members",
        "ix_family_members_status": "family_members",
        "ix_leases_owner_person_id": "leases",
        "ix_residents_status": "residents",
    }
    for index_name, table_name in expected_indexes.items():
        assert index_name in {index.name for index in Base.metadata.tables[table_name].indexes}

    family_society_fks = {
        tuple(foreign_key.column_keys)
        for foreign_key in Base.metadata.tables["family_members"].foreign_key_constraints
        if foreign_key.referred_table.name == "societies"
    }
    assert ("society_id",) in family_society_fks

    units = Base.metadata.tables["units"]
    ownerships = Base.metadata.tables["ownerships"]
    units_ddl = str(CreateTable(units).compile(dialect=postgresql.dialect()))
    ownerships_ddl = str(CreateTable(ownerships).compile(dialect=postgresql.dialect()))
    assert "CONSTRAINT uq_units_society_id UNIQUE (society_id, unit_id)" in units_ddl
    assert "FOREIGN KEY(society_id, unit_id) REFERENCES units (society_id, unit_id)" in ownerships_ddl
    table_order = [table.name for table in Base.metadata.sorted_tables]
    assert table_order.index("units") < table_order.index("ownerships")


def test_postgresql_btree_gist_supports_occupancy_exclusion(engine) -> None:
    with engine.connect() as connection:
        current_schema = connection.execute(text("SELECT current_schema()")).scalar_one()
        resolved_schema = connection.execute(
            text(
                "SELECT n.nspname "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE c.oid = to_regclass('units')"
            )
        ).scalar_one()
        extension_exists = connection.execute(
            text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'btree_gist')")
        ).scalar_one()
        exclusion_exists = connection.execute(
            text(
                "SELECT EXISTS ("
                "SELECT 1 FROM pg_constraint "
                "JOIN pg_class r ON r.oid = pg_constraint.conrelid "
                "JOIN pg_namespace n ON n.oid = r.relnamespace "
                "WHERE n.nspname = :schema_name AND r.relname = 'occupancy_history' "
                "AND conname = 'ex_occupancy_history_active_person_unit_dates'"
                ")"
            ),
            {"schema_name": current_schema},
        ).scalar_one()

    assert resolved_schema == current_schema
    assert extension_exists is True
    assert exclusion_exists is True


def test_occupancy_allows_household_people_and_rejects_same_person_overlap(engine) -> None:
    with engine.begin() as connection:
        society_id, unit_id, _, person_a, person_b = _property_fixture(connection)
        person_c = uuid4()
        connection.execute(
            text("INSERT INTO persons (person_id, full_name, status) VALUES (:id, 'Single day resident', 'ACTIVE')"),
            {"id": person_c},
        )
        for person_id, start in ((person_a, "2026-01-01"), (person_b, "2026-02-01")):
            connection.execute(
                text("INSERT INTO occupancy_history (occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, status) VALUES (:id, :society_id, :unit_id, :person_id, 'RESIDENT', :start, 'ACTIVE')"),
                {"id": uuid4(), "society_id": society_id, "unit_id": unit_id, "person_id": person_id, "start": start},
            )
        # The end date is the inclusive last occupied day. A single-day stay
        # is valid, a new stay on that same day overlaps, and the next day is
        # an acceptable successor period.
        connection.execute(
            text("INSERT INTO occupancy_history (occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, move_out_date, status) VALUES (:id, :society_id, :unit_id, :person_id, 'RESIDENT', '2030-01-01', '2030-01-01', 'ACTIVE')"),
            {"id": uuid4(), "society_id": society_id, "unit_id": unit_id, "person_id": person_c},
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO occupancy_history (occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, status) VALUES (:id, :society_id, :unit_id, :person_id, 'RESIDENT', '2030-01-01', 'ACTIVE')"),
                {"id": uuid4(), "society_id": society_id, "unit_id": unit_id, "person_id": person_c},
            )

    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO occupancy_history (occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, status) VALUES (:id, :society_id, :unit_id, :person_id, 'RESIDENT', '2030-01-02', 'ACTIVE')"),
            {"id": uuid4(), "society_id": society_id, "unit_id": unit_id, "person_id": person_c},
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO occupancy_history (occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, move_out_date, status) VALUES (:id, :society_id, :unit_id, :person_id, 'RESIDENT', '2026-03-01', '2026-04-01', 'ACTIVE')"),
                {"id": uuid4(), "society_id": society_id, "unit_id": unit_id, "person_id": person_a},
            )

    with engine.begin() as connection:
        connection.execute(
            text("UPDATE occupancy_history SET move_out_date = '2026-06-01' WHERE society_id = :society_id AND person_id = :person_id"),
            {"society_id": society_id, "person_id": person_a},
        )
        connection.execute(
            text("INSERT INTO occupancy_history (occupancy_id, society_id, unit_id, person_id, occupancy_type, move_in_date, status) VALUES (:id, :society_id, :unit_id, :person_id, 'RESIDENT', '2026-06-02', 'ACTIVE')"),
            {"id": uuid4(), "society_id": society_id, "unit_id": unit_id, "person_id": person_a},
        )


def test_deleting_unit_type_nulls_only_type_id(engine) -> None:
    with engine.begin() as connection:
        _, unit_id, unit_type_id, _, _ = _property_fixture(connection)
        connection.execute(text("DELETE FROM unit_types WHERE unit_type_id = :id"), {"id": unit_type_id})
        row = connection.execute(text("SELECT society_id, unit_type_id FROM units WHERE unit_id = :id"), {"id": unit_id}).mappings().one()
        assert row["society_id"] is not None
        assert row["unit_type_id"] is None


def test_vehicle_and_emergency_contact_lifecycle_constraints(engine) -> None:
    with engine.begin() as connection:
        society_id, unit_id, _, person_a, person_b = _property_fixture(connection)
        resident_id = uuid4()
        vehicle_id = uuid4()
        linked_contact_id = uuid4()
        external_contact_id = uuid4()

        connection.execute(
            text(
                "INSERT INTO residents "
                "(resident_id, society_id, unit_id, person_id, resident_type, is_primary, status) "
                "VALUES (:resident_id, :society_id, :unit_id, :person_id, 'OWNER', false, 'ACTIVE')"
            ),
            {
                "resident_id": resident_id,
                "society_id": society_id,
                "unit_id": unit_id,
                "person_id": person_b,
            },
        )
        connection.execute(
            text(
                "INSERT INTO vehicles "
                "(vehicle_id, society_id, unit_id, person_id, registration_number, vehicle_type, status) "
                "VALUES (:vehicle_id, :society_id, :unit_id, :person_id, 'MH12-UAT-1234', 'CAR', 'ACTIVE')"
            ),
            {
                "vehicle_id": vehicle_id,
                "society_id": society_id,
                "unit_id": unit_id,
                "person_id": person_a,
            },
        )
        for contact_id, linked_person_id, name in (
            (linked_contact_id, person_a, "Linked contact"),
            (external_contact_id, None, "External contact"),
        ):
            connection.execute(
                text(
                    "INSERT INTO emergency_contacts "
                    "(emergency_contact_id, society_id, resident_id, person_id, name, mobile) "
                    "VALUES (:contact_id, :society_id, :resident_id, :person_id, :name, '9876543210')"
                ),
                {
                    "contact_id": contact_id,
                    "society_id": society_id,
                    "resident_id": resident_id,
                    "person_id": linked_person_id,
                    "name": name,
                },
            )

    # A deleted person is detached from the vehicle/contact records, preserving those records.
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM persons WHERE person_id = :id"), {"id": person_a})
        vehicle = connection.execute(
            text("SELECT person_id, unit_id FROM vehicles WHERE vehicle_id = :id"),
            {"id": vehicle_id},
        ).mappings().one()
        linked_contact = connection.execute(
            text("SELECT person_id, name FROM emergency_contacts WHERE emergency_contact_id = :id"),
            {"id": linked_contact_id},
        ).mappings().one()
        external_contact = connection.execute(
            text("SELECT person_id, name FROM emergency_contacts WHERE emergency_contact_id = :id"),
            {"id": external_contact_id},
        ).mappings().one()

        assert vehicle["person_id"] is None
        assert vehicle["unit_id"] == unit_id
        assert linked_contact["person_id"] is None
        assert linked_contact["name"] == "Linked contact"
        assert external_contact["person_id"] is None
        assert external_contact["name"] == "External contact"

        connection.execute(text("DELETE FROM residents WHERE resident_id = :id"), {"id": resident_id})
        assert connection.execute(
            text("SELECT count(*) FROM emergency_contacts WHERE resident_id = :id"),
            {"id": resident_id},
        ).scalar_one() == 0

        connection.execute(text("DELETE FROM units WHERE unit_id = :id"), {"id": unit_id})
        assert connection.execute(
            text("SELECT count(*) FROM vehicles WHERE vehicle_id = :id"),
            {"id": vehicle_id},
        ).scalar_one() == 0


def test_vehicles_reject_duplicate_society_registration_and_cross_society_unit(engine) -> None:
    with engine.begin() as connection:
        society_a, unit_a, _, person_a, _ = _property_fixture(connection)
        society_b, unit_b, _, _, _ = _property_fixture(connection)
        connection.execute(
            text(
                "INSERT INTO vehicles "
                "(vehicle_id, society_id, unit_id, person_id, registration_number, vehicle_type, status) "
                "VALUES (:id, :society_id, :unit_id, :person_id, 'MH12-UAT-5678', 'CAR', 'ACTIVE')"
            ),
            {"id": uuid4(), "society_id": society_a, "unit_id": unit_a, "person_id": person_a},
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO vehicles "
                    "(vehicle_id, society_id, unit_id, registration_number, vehicle_type, status) "
                    "VALUES (:id, :society_id, :unit_id, 'MH12-UAT-5678', 'CAR', 'ACTIVE')"
                ),
                {"id": uuid4(), "society_id": society_a, "unit_id": unit_a},
            )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO vehicles "
                    "(vehicle_id, society_id, unit_id, registration_number, vehicle_type, status) "
                    "VALUES (:id, :society_id, :unit_id, 'MH12-UAT-9999', 'CAR', 'ACTIVE')"
                ),
                {"id": uuid4(), "society_id": society_a, "unit_id": unit_b},
            )


def test_active_lease_overlap_and_ownership_share_rules_are_database_enforced(engine) -> None:
    # Set up one flat, two people, an existing lease, and 60% ownership.
    with engine.begin() as connection:
        society_id, unit_id, _, person_a, person_b = _property_fixture(connection)

        connection.execute(
            text(
                "INSERT INTO leases "
                "(lease_id, society_id, unit_id, tenant_person_id, "
                "lease_start, lease_end, status) "
                "VALUES (:id, :society_id, :unit_id, :person_id, "
                "'2026-01-01', '2026-06-01', 'ACTIVE')"
            ),
            {
                "id": uuid4(),
                "society_id": society_id,
                "unit_id": unit_id,
                "person_id": person_a,
            },
        )

        connection.execute(
            text(
                "INSERT INTO ownerships "
                "(ownership_id, society_id, unit_id, person_id, "
                "share_percentage, start_date, status) "
                "VALUES (:id, :society_id, :unit_id, :person_id, "
                "60, '2026-01-01', 'ACTIVE')"
            ),
            {
                "id": uuid4(),
                "society_id": society_id,
                "unit_id": unit_id,
                "person_id": person_a,
            },
        )

    # Overlapping active lease for a different tenant must be rejected.
    with pytest.raises(IntegrityError, match="ex_leases_active_unit_dates"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO leases "
                    "(lease_id, society_id, unit_id, tenant_person_id, "
                    "lease_start, lease_end, status) "
                    "VALUES (:id, :society_id, :unit_id, :person_id, "
                    "'2026-06-01', '2026-07-01', 'ACTIVE')"
                ),
                {
                    "id": uuid4(),
                    "society_id": society_id,
                    "unit_id": unit_id,
                    "person_id": person_b,
                },
            )

    # A new tenant may lease the flat after the previous lease ends.
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO leases "
                "(lease_id, society_id, unit_id, tenant_person_id, "
                "lease_start, lease_end, status) "
                "VALUES (:id, :society_id, :unit_id, :person_id, "
                "'2026-06-02', '2026-12-31', 'ACTIVE')"
            ),
            {
                "id": uuid4(),
                "society_id": society_id,
                "unit_id": unit_id,
                "person_id": person_b,
            },
        )

    # An individual ownership share above 100% must be rejected.
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO ownerships "
                    "(ownership_id, society_id, unit_id, person_id, "
                    "share_percentage, start_date, status) "
                    "VALUES (:id, :society_id, :unit_id, :person_id, "
                    "101, '2026-01-01', 'ACTIVE')"
                ),
                {
                    "id": uuid4(),
                    "society_id": society_id,
                    "unit_id": unit_id,
                    "person_id": person_b,
                },
            )
