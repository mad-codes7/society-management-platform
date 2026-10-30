from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Iterator
from uuid import uuid4

import pytest
from dotenv import dotenv_values
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session
from starlette.testclient import TestClient


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
NORMAL_DATABASE_URL = os.environ.get("DATABASE_URL") or dotenv_values(
    BACKEND_ROOT / ".env"
).get("DATABASE_URL")


def _describe_database(raw_url: str | None) -> str:
    if not raw_url:
        return "<unset>"
    try:
        url = make_url(raw_url)
    except Exception:
        return "<unparseable URL; credentials redacted>"
    return (
        f"host={url.host or '<local-socket>'} "
        f"port={url.port or '<default>'} "
        f"database={url.database or '<unset>'} "
        "credentials=<redacted>"
    )


def _database_identity(url: URL) -> tuple[str, str, int | None, str | None]:
    return (
        url.get_backend_name(),
        (url.host or "").lower(),
        url.port,
        url.database,
    )


print(f"Resolved TEST_DATABASE_URL: {_describe_database(TEST_DATABASE_URL)}", flush=True)
print(f"Resolved DATABASE_URL: {_describe_database(NORMAL_DATABASE_URL)}", flush=True)

if not TEST_DATABASE_URL:
    raise pytest.UsageError(
        "TEST_DATABASE_URL is required. Configure it to point to a dedicated "
        "PostgreSQL test database; no tests or database connections were started."
    )

if not NORMAL_DATABASE_URL:
    raise pytest.UsageError(
        "DATABASE_URL could not be resolved from the environment or backend/.env, "
        "so the test database cannot be checked for separation."
    )

try:
    _test_url = make_url(TEST_DATABASE_URL)
    _normal_url = make_url(NORMAL_DATABASE_URL)
except Exception:
    raise pytest.UsageError(
        "Invalid database URL configuration; check both URLs without exposing credentials."
    ) from None

if _database_identity(_test_url) == _database_identity(_normal_url):
    raise pytest.UsageError(
        "TEST_DATABASE_URL resolves to the same database as DATABASE_URL. "
        "Use a separate test database; no tests or database connections were started."
    )

if _test_url.get_backend_name() != "postgresql":
    raise pytest.UsageError(
        "TEST_DATABASE_URL must use PostgreSQL to match the project's UUID and "
        "dialect-specific model definitions."
    )

# Ensure application settings and its engine use only the guarded test target.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("JWT_SECRET_KEY", "pytest-only-not-a-production-secret")


@pytest.fixture(scope="session")
def engine():
    import app.models  # noqa: F401
    from app.models.base import Base

    database_url = _test_url
    if database_url.drivername == "postgresql":
        database_url = database_url.set(drivername="postgresql+psycopg")

    schema_name = f"pytest_{uuid4().hex}"
    bootstrap_engine = create_engine(database_url, pool_pre_ping=True)
    with bootstrap_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public"))
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    bootstrap_engine.dispose()

    test_engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(test_engine, "checkout")
    def set_test_schema(dbapi_connection, _connection_record, _connection_proxy) -> None:
        if os.environ.get("PGOPTIONS"):
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f'SET search_path TO "{schema_name}", public')
        finally:
            cursor.close()
        dbapi_connection.commit()

    with test_engine.begin() as connection:
        isolated_connection = connection.execution_options(
            schema_translate_map={None: schema_name}
        )
        Base.metadata.create_all(isolated_connection)
    try:
        yield test_engine
    finally:
        test_engine.dispose()
        cleanup_engine = create_engine(database_url, pool_pre_ping=True)
        with cleanup_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        cleanup_engine.dispose()


@pytest.fixture(scope="module")
def alembic_engine() -> Iterator:
    """Create an isolated schema using the actual Alembic migration chain."""
    database_url = _test_url
    if database_url.drivername == "postgresql":
        database_url = database_url.set(drivername="postgresql+psycopg")

    schema_name = f"pytest_migrated_{uuid4().hex}"
    bootstrap_engine = create_engine(database_url, pool_pre_ping=True)
    with bootstrap_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public"))
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    bootstrap_engine.dispose()

    environment = os.environ.copy()
    environment["PGOPTIONS"] = f"-csearch_path={schema_name},public"
    migration = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            "head",
        ],
        cwd=BACKEND_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if migration.returncode != 0:
        cleanup_engine = create_engine(database_url, pool_pre_ping=True)
        with cleanup_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        cleanup_engine.dispose()
        pytest.fail(
            "Alembic upgrade head failed in isolated migrated test schema.\n"
            f"stdout:\n{migration.stdout}\nstderr:\n{migration.stderr}"
        )

    migrated_engine = create_engine(database_url, pool_pre_ping=True)

    @event.listens_for(migrated_engine, "checkout")
    def set_migrated_test_schema(
        dbapi_connection, _connection_record, _connection_proxy
    ) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f'SET search_path TO "{schema_name}", public')
        finally:
            cursor.close()
        dbapi_connection.commit()

    try:
        yield migrated_engine
    finally:
        migrated_engine.dispose()
        cleanup_engine = create_engine(database_url, pool_pre_ping=True)
        with cleanup_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        cleanup_engine.dispose()


@pytest.fixture
def db_session(engine) -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    from app.core.database import get_db
    from app.main import app

    def override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)