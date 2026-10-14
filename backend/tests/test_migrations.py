from __future__ import annotations

import os
import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text


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