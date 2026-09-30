from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


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
            assert {"alembic_version", "persons", "societies", "users", "society_memberships"} <= table_names
    finally:
        if previous_pgoptions is None:
            os.environ.pop("PGOPTIONS", None)
        else:
            os.environ["PGOPTIONS"] = previous_pgoptions

        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
