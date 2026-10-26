from __future__ import annotations

import os
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_v2_occupancy_insert_parameters_have_exact_uuid_bind_key() -> None:
    migration_path = BACKEND_ROOT / "alembic/versions/b7c8d9e0f1a2_phase1_v2_society_core.py"
    spec = importlib.util.spec_from_file_location("phase1_v2_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)

    rows = [
        {
            "society_id": uuid4(),
            "unit_id": uuid4(),
            "person_id": uuid4(),
            "resident_type": "OWNER",
            "move_in_date": "2026-01-01",
            "move_out_date": None,
            "occupancy_status": "ACTIVE",
        },
        {
            "society_id": uuid4(),
            "unit_id": uuid4(),
            "person_id": uuid4(),
            "resident_type": "TENANT",
            "move_in_date": "2026-02-01",
            "move_out_date": "2026-03-01",
            "occupancy_status": "INACTIVE",
        },
    ]
    parameters = list(migration._occupancy_history_parameters(rows))

    assert all(isinstance(item["occupancy_id"], type(uuid4())) for item in parameters)
    assert len({item["occupancy_id"] for item in parameters}) == len(parameters)
    assert all("occupancy_id" in item for item in parameters)


def test_alembic_head_upgrades_in_isolated_schema(engine: Engine) -> None:
    schema_name = f"migration_smoke_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    previous_pgoptions = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = f"-csearch_path={schema_name}"
    try:
        alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "head")

        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            table_names = set(inspect(connection).get_table_names())
            lease_constraint = connection.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = :schema_name
                    AND t.relname = 'leases'
                    AND c.conname = 'ex_leases_active_unit_dates'
                    """
                ),
                {"schema_name": schema_name},
            ).scalar_one()

            assert "unit_id WITH =" in lease_constraint
            assert "tenant_person_id WITH =" not in lease_constraint
            assert {
                "alembic_version",
                "persons",
                "societies",
                "users",
                "society_memberships",
                "roles",
                "permissions",
                "role_permissions",
                "user_roles",
                "audit_logs",
            } <= table_names
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions

        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            
        # Kill pooled connections that were pointing to the dropped schema
        engine.dispose()


def test_v2_backfills_unlinked_users_without_changing_authentication_data(engine: Engine) -> None:
    schema_name = f"migration_v2_users_{uuid4().hex}"
    matching_person_id = uuid4()
    matching_user_id = uuid4()
    unlinked_user_id = uuid4()
    matching_password_hash = "matching-password-hash"
    unlinked_password_hash = "unlinked-password-hash"
    matching_email = f"existing-person-{uuid4().hex}@example.com"
    unlinked_email = f"platform-admin-{uuid4().hex}@example.com"

    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    previous_pgoptions = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = f"-csearch_path={schema_name}"
    try:
        alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "a1b2c3d4e5f6")
        with engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(
                text(
                    "INSERT INTO persons (person_id, first_name, last_name, email) "
                    "VALUES (:person_id, 'Existing', 'Person', :email)"
                ),
                {"person_id": matching_person_id, "email": matching_email},
            )
            connection.execute(
                text(
                    "INSERT INTO users (user_id, person_id, email, password_hash, is_active, is_super_admin) "
                    "VALUES (:user_id, NULL, :email, :password_hash, true, false)"
                ),
                {
                    "user_id": matching_user_id,
                    "email": matching_email,
                    "password_hash": matching_password_hash,
                },
            )
            connection.execute(
                text(
                    "INSERT INTO users (user_id, person_id, email, password_hash, is_active, is_super_admin) "
                    "VALUES (:user_id, NULL, :email, :password_hash, true, true)"
                ),
                {
                    "user_id": unlinked_user_id,
                    "email": unlinked_email,
                    "password_hash": unlinked_password_hash,
                },
            )

        command.upgrade(alembic_config, "head")

        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            matching = connection.execute(
                text(
                    "SELECT person_id, email, password_hash, is_super_admin "
                    "FROM users WHERE user_id = :user_id"
                ),
                {"user_id": matching_user_id},
            ).mappings().one()
            generated = connection.execute(
                text(
                    "SELECT u.person_id, u.email, u.password_hash, u.is_super_admin, "
                    "p.full_name, p.email AS person_email "
                    "FROM users u JOIN persons p ON p.person_id = u.person_id "
                    "WHERE u.user_id = :user_id"
                ),
                {"user_id": unlinked_user_id},
            ).mappings().one()

        assert matching["person_id"] == matching_person_id
        assert matching["password_hash"] == matching_password_hash
        assert generated["full_name"] == unlinked_email
        assert generated["person_email"] == unlinked_email
        assert generated["password_hash"] == unlinked_password_hash
        assert generated["is_super_admin"] is True
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions

        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
            
        # Kill pooled connections that were pointing to the dropped schema
        engine.dispose()


def test_review_corrections_preserve_legacy_role_and_settings_data(engine: Engine) -> None:
    schema_name = f"migration_review_{uuid4().hex}"
    society_id = uuid4()
    role_id = uuid4()
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    previous_pgoptions = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = f"-csearch_path={schema_name}"
    try:
        alembic_config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(alembic_config, "c9d0e1f2a3b4")
        with engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(
                text("INSERT INTO societies (society_id, name, status) VALUES (:id, 'Legacy Review Society', 'ACTIVE')"),
                {"id": society_id},
            )
            connection.execute(
                text("INSERT INTO roles (role_id, name, description, is_active) VALUES (:id, 'Legacy Treasurer', 'Preserve me', true)"),
                {"id": role_id},
            )
            connection.execute(
                text("INSERT INTO society_settings (setting_id, society_id, late_fee_rule, grace_period_days, due_day) VALUES (:id, :society_id, '{\"kind\": \"fixed\", \"amount\": 25}', 7, 10)"),
                {"id": uuid4(), "society_id": society_id},
            )

        command.upgrade(alembic_config, "head")

        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            role = connection.execute(
                text("SELECT code, description FROM roles WHERE role_id = :id"), {"id": role_id}
            ).mappings().one()
            settings = connection.execute(
                text("SELECT late_fee_rule, grace_period_days, due_day FROM society_settings WHERE society_id = :id"),
                {"id": society_id},
            ).mappings().one()

        assert role["code"] == "legacy_treasurer"
        assert role["description"] == "Preserve me"
        assert settings["late_fee_rule"] == {"kind": "fixed", "amount": 25}
        assert settings["grace_period_days"] == 7
        assert settings["due_day"] == 10
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions

        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))

        engine.dispose()


def test_pre_v2_household_occupancy_migrates_to_head(engine: Engine) -> None:
    schema_name = f"migration_household_{uuid4().hex}"
    society_id, building_id, floor_id, unit_type_id, unit_id = (uuid4() for _ in range(5))
    residents = [(uuid4(), uuid4()), (uuid4(), uuid4())]
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    previous_pgoptions = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = f"-csearch_path={schema_name}"
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(config, "a1b2c3d4e5f6")
        with engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(text("INSERT INTO societies (society_id,name,status,created_at,updated_at) VALUES (:id,'Household migration','ACTIVE',now(),now())"), {"id": society_id})
            connection.execute(text("INSERT INTO buildings (building_id,society_id,name,code,building_type,total_floors) VALUES (:id,:society,'A','A','TOWER',1)"), {"id": building_id, "society": society_id})
            connection.execute(text("INSERT INTO floors (floor_id,building_id,floor_number) VALUES (:id,:building,1)"), {"id": floor_id, "building": building_id})
            connection.execute(text("INSERT INTO unit_types (unit_type_id,society_id,name) VALUES (:id,:society,'Flat')"), {"id": unit_type_id, "society": society_id})
            connection.execute(text("INSERT INTO units (unit_id,society_id,building_id,floor_id,unit_type_id,unit_number) VALUES (:id,:society,:building,:floor,:type,'101')"), {"id": unit_id, "society": society_id, "building": building_id, "floor": floor_id, "type": unit_type_id})
            for index, (person_id, resident_id) in enumerate(residents):
                connection.execute(text("INSERT INTO persons (person_id,first_name,last_name) VALUES (:id,:first,'Resident')"), {"id": person_id, "first": f"Person{index}"})
                connection.execute(text("INSERT INTO residents (resident_id,society_id,unit_id,person_id,resident_type,occupancy_status,move_in_date) VALUES (:resident,:society,:unit,:person,'OWNER','ACTIVE','2026-01-01')"), {"resident": resident_id, "society": society_id, "unit": unit_id, "person": person_id})

        command.upgrade(config, "head")
        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            migrated_people = set(
                connection.execute(
                    text(
                        "SELECT person_id FROM occupancy_history "
                        "WHERE unit_id=:unit AND status='ACTIVE'"
                    ),
                    {"unit": unit_id},
                ).scalars()
            )
            assert migrated_people == {person_id for person_id, _ in residents}
            exclusion = connection.execute(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='occupancy_history'::regclass AND conname='ex_occupancy_history_active_person_unit_dates'")).scalar_one()
            assert "society_id WITH =" in exclusion
            assert "unit_id WITH =" in exclusion
            assert "person_id WITH =" in exclusion
            assert connection.execute(text("SELECT count(*) FROM pg_constraint WHERE conrelid='occupancy_history'::regclass AND conname='ex_occupancy_history_active_unit_dates'")).scalar_one() == 0
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()


def test_review_corrections_downgrade_requires_pre_correction_backup(engine: Engine) -> None:
    schema_name = f"migration_review_downgrade_{uuid4().hex}"
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))

    previous_pgoptions = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = f"-csearch_path={schema_name}"
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(config, "d4e5f6a7b8c9")

        with pytest.raises(RuntimeError) as error:
            command.downgrade(config, "c9d0e1f2a3b4")

        assert str(error.value) == (
            "Cannot downgrade Phase 1 review corrections safely: restoring the legacy "
            "unit-only occupancy exclusion rejects valid household occupancy. Restore "
            "a verified pre-correction backup instead. No downgrade operations were run."
        )

        with engine.connect() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == "d4e5f6a7b8c9"
            assert connection.execute(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid='occupancy_history'::regclass "
                    "AND conname='ex_occupancy_history_active_unit_dates'"
                )
            ).scalar_one() == 0
            assert connection.execute(
                text(
                    "SELECT count(*) FROM pg_constraint "
                    "WHERE conrelid='occupancy_history'::regclass "
                    "AND conname='ex_occupancy_history_active_person_unit_dates'"
                )
            ).scalar_one() == 1
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()


def test_ownership_aggregate_validation_enforces_periods_and_updates(engine: Engine) -> None:
    schema_name = f"migration_ownership_{uuid4().hex}"
    society_id, building_id, floor_id, unit_id, unit2_id = (uuid4() for _ in range(5))
    person_ids = [uuid4() for _ in range(3)]
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    previous_pgoptions = os.environ.get("PGOPTIONS")
    os.environ["PGOPTIONS"] = f"-csearch_path={schema_name}"
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(config, "head")
        with engine.begin() as connection:
            connection.execute(text(f'SET search_path TO "{schema_name}"'))
            connection.execute(text("INSERT INTO societies (society_id,name,status,created_at,updated_at) VALUES (:id,'Ownership migration','ACTIVE',now(),now())"), {"id": society_id})
            connection.execute(text("INSERT INTO buildings (building_id,society_id,name) VALUES (:id,:society,'A')"), {"id": building_id, "society": society_id})
            connection.execute(text("INSERT INTO floors (floor_id,building_id,floor_number) VALUES (:id,:building,1)"), {"id": floor_id, "building": building_id})
            for unit_id_value, number in ((unit_id, "101"), (unit2_id, "102")):
                connection.execute(text("INSERT INTO units (unit_id,society_id,building_id,floor_id,unit_number) VALUES (:id,:society,:building,:floor,:number)"), {"id": unit_id_value, "society": society_id, "building": building_id, "floor": floor_id, "number": number})
            for person_id in person_ids:
                connection.execute(text("INSERT INTO persons (person_id,full_name) VALUES (:id,'Owner')"), {"id": person_id})
            def ownership(unit, person, share, start, end=None, status="ACTIVE"):
                ownership_id = uuid4()
                connection.execute(text("INSERT INTO ownerships (ownership_id,society_id,unit_id,person_id,share_percentage,start_date,end_date,status) VALUES (:id,:society,:unit,:person,:share,:start,:end,:status)"), {"id": ownership_id, "society": society_id, "unit": unit, "person": person, "share": share, "start": start, "end": end, "status": status})
                return ownership_id

            ownership(unit_id, person_ids[0], 40, "2026-01-01", "2026-01-31")
            ownership(unit_id, person_ids[1], 60, "2026-01-01", "2026-01-31")
            february_ownership_id = ownership(unit_id, person_ids[2], 100, "2026-02-01", "2026-02-28")
            ownership(unit2_id, person_ids[0], 60, "2026-01-01")

        with pytest.raises(IntegrityError, match="exceed 100%"):
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO ownerships (ownership_id,society_id,unit_id,person_id,share_percentage,start_date,status) VALUES (:id,:society,:unit,:person,41,'2026-01-15','ACTIVE')"), {"id": uuid4(), "society": society_id, "unit": unit_id, "person": person_ids[2]})
        # Jan 31 remains covered by the 40% and 60% rows; Feb 1 is the first
        # day after their inclusive end and starts a valid historical period.
        with pytest.raises(IntegrityError, match="exceed 100%"):
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO ownerships (ownership_id,society_id,unit_id,person_id,share_percentage,start_date,end_date,status) VALUES (:id,:society,:unit,:person,1,'2026-01-31','2026-01-31','ACTIVE')"), {"id": uuid4(), "society": society_id, "unit": unit_id, "person": person_ids[2]})

        with engine.begin() as connection:
            connection.execute(text("INSERT INTO ownerships (ownership_id,society_id,unit_id,person_id,share_percentage,start_date,status) VALUES (:id,:society,:unit,:person,40,'2026-01-01','INACTIVE')"), {"id": uuid4(), "society": society_id, "unit": unit2_id, "person": person_ids[1]})
        with pytest.raises(IntegrityError, match="exceed 100%"):
            with engine.begin() as connection:
                connection.execute(text("UPDATE ownerships SET status='ACTIVE', share_percentage=41 WHERE unit_id=:unit AND person_id=:person"), {"unit": unit2_id, "person": person_ids[1]})
        with pytest.raises(IntegrityError, match="exceed 100%"):
            with engine.begin() as connection:
                connection.execute(text("UPDATE ownerships SET unit_id=:new_unit WHERE unit_id=:unit AND person_id=:person"), {"new_unit": unit_id, "unit": unit2_id, "person": person_ids[0]})

        # Removing a valid ownership row is allowed and is checked by the same
        # database trigger. The freed historical period can then be reassigned.
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM ownerships WHERE ownership_id=:id"), {"id": february_ownership_id})
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO ownerships (ownership_id,society_id,unit_id,person_id,share_percentage,start_date,end_date,status) VALUES (:id,:society,:unit,:person,100,'2026-02-01','2026-02-28','ACTIVE')"), {"id": uuid4(), "society": society_id, "unit": unit_id, "person": person_ids[0]})

        # Two concurrent inserts would total 120% after the existing 0% March
        # balance. The advisory lock and deferred check must allow only one.
        barrier = Barrier(2)

        def insert_concurrent_share(person_id):
            try:
                with engine.begin() as connection:
                    barrier.wait(timeout=10)
                    connection.execute(text("INSERT INTO ownerships (ownership_id,society_id,unit_id,person_id,share_percentage,start_date,status) VALUES (:id,:society,:unit,:person,60,'2026-03-01','ACTIVE')"), {"id": uuid4(), "society": society_id, "unit": unit_id, "person": person_id})
                return True
            except IntegrityError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(insert_concurrent_share, person_ids[1:3]))
        assert sorted(outcomes) == [False, True]
        with engine.connect() as connection:
            active_march_shares = connection.execute(text("SELECT sum(share_percentage) FROM ownerships WHERE unit_id=:unit AND status='ACTIVE' AND start_date='2026-03-01'"), {"unit": unit_id}).scalar_one()
        assert active_march_shares == 60
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        engine.dispose()
