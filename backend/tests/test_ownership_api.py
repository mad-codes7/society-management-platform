from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.history import Ownership
from app.models.person import Person, Resident
from app.models.property import Building, Floor, Unit
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.society import Society
from app.models.user import SocietyMembership, User
from test_auth_tenancy import bearer_headers


@pytest.fixture(scope="module")
def engine():
    test_database_url = os.environ["TEST_DATABASE_URL"]
    test_url = make_url(test_database_url)

    if test_url.drivername == "postgresql":
        test_url = test_url.set(drivername="postgresql+psycopg")
    schema_name = f"pytest_ownership_{uuid4().hex}"
    bootstrap_engine = create_engine(test_url, pool_pre_ping=True)
    with bootstrap_engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist WITH SCHEMA public"))
        connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
    bootstrap_engine.dispose()

    migrated_url = test_url.render_as_string(hide_password=False)
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = migrated_url
    migration_environment["PGOPTIONS"] = f"-c search_path={schema_name},public"
    backend_root = Path(__file__).resolve().parents[1]
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=backend_root,
        env=migration_environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if migration.returncode != 0:
        cleanup_engine = create_engine(test_url, pool_pre_ping=True)
        with cleanup_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        cleanup_engine.dispose()
        pytest.fail(
            "Alembic upgrade head failed in isolated ownership-test schema.\n"
            f"stdout:\n{migration.stdout}\nstderr:\n{migration.stderr}"
        )

    test_engine = create_engine(test_url, pool_pre_ping=True)

    @event.listens_for(test_engine, "checkout")
    def set_ownership_test_schema(dbapi_connection, _connection_record, _connection_proxy):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute(f'SET search_path TO "{schema_name}", public')
        finally:
            cursor.close()
        dbapi_connection.commit()

    try:
        yield test_engine
    finally:
        test_engine.dispose()
        cleanup_engine = create_engine(test_url, pool_pre_ping=True)
        with cleanup_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema_name}" CASCADE'))
        cleanup_engine.dispose()


def test_ownership_api_fixture_uses_migrated_share_validation(engine) -> None:
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        triggers = {
            row.tgname: (row.tgdeferrable, row.tginitdeferred)
            for row in connection.execute(
                text(
                    """
                    SELECT tgname, tgdeferrable, tginitdeferred
                    FROM pg_trigger
                    WHERE tgrelid = 'ownerships'::regclass
                      AND NOT tgisinternal
                    """
                )
            )
        }

    assert revision == "f1a2b3c4d5e6"
    assert triggers["ownerships_serialize_writes"] == (False, False)
    assert triggers["ownerships_validate_share_totals"] == (True, True)


@pytest.fixture
def ownership_tenant_data(db_session: Session) -> dict[str, object]:
    suffix = uuid4().hex
    society_a = Society(name=f"Ownership Tenant A {suffix}", status="ACTIVE")
    society_b = Society(name=f"Ownership Tenant B {suffix}", status="ACTIVE")
    user = User(
        person=Person(full_name="Ownership Test User"),
        email=f"ownership-{suffix}@example.com",
        password_hash=hash_password("Test-Only-Password-1!"),
        is_active=True,
    )
    db_session.add_all([society_a, society_b, user])
    db_session.flush()
    db_session.add(
        SocietyMembership(
            user_id=user.user_id,
            society_id=society_a.society_id,
            status="ACTIVE",
        )
    )

    building_a = Building(
        society_id=society_a.society_id,
        name="Ownership Tower A",
        code=f"A-{suffix[:8]}",
        total_floors=1,
    )
    building_b = Building(
        society_id=society_b.society_id,
        name="Ownership Tower B",
        code=f"B-{suffix[:8]}",
        total_floors=1,
    )
    db_session.add_all([building_a, building_b])
    db_session.flush()
    floor_a = Floor(building_id=building_a.building_id, floor_number=1)
    floor_b = Floor(building_id=building_b.building_id, floor_number=1)
    db_session.add_all([floor_a, floor_b])
    db_session.flush()
    unit_a = Unit(
        society_id=society_a.society_id,
        building_id=building_a.building_id,
        floor_id=floor_a.floor_id,
        unit_number="A-101",
    )
    unit_b = Unit(
        society_id=society_b.society_id,
        building_id=building_b.building_id,
        floor_id=floor_b.floor_id,
        unit_number="B-101",
    )
    people = [
        Person(full_name=f"Ownership Person {index} {suffix}")
        for index in range(1, 5)
    ]
    db_session.add_all([unit_a, unit_b, *people])
    db_session.flush()
    db_session.add_all(
        [
            Resident(
                society_id=society_a.society_id,
                unit_id=unit_a.unit_id,
                person_id=person.person_id,
                resident_type="OWNER",
                status="ACTIVE",
            )
            for person in people[:3]
        ]
        + [
            Resident(
                society_id=society_b.society_id,
                unit_id=unit_b.unit_id,
                person_id=people[3].person_id,
                resident_type="OWNER",
                status="ACTIVE",
            )
        ]
    )
    db_session.flush()

    return {
        "society_a": society_a,
        "society_b": society_b,
        "user": user,
        "unit_a": unit_a,
        "unit_b": unit_b,
        "people": people,
    }


def grant_property_permissions(
    db_session: Session,
    user: User,
    society_id,
    *codes: str,
) -> None:
    role = Role(
        name=f"Ownership Test Role {uuid4().hex}",
        code=f"ownership_test_{uuid4().hex}",
        is_active=True,
    )
    db_session.add(role)
    db_session.flush()
    for code in codes:
        permission = db_session.scalar(
            select(Permission).where(Permission.code == code)
        )
        if permission is None:
            permission = Permission(code=code, module="property")
            db_session.add(permission)
            db_session.flush()
        db_session.add(
            RolePermission(role_id=role.role_id, permission_id=permission.permission_id)
        )
    membership = db_session.scalar(
        select(SocietyMembership).where(
            SocietyMembership.user_id == user.user_id,
            SocietyMembership.society_id == society_id,
        )
    )
    assert membership is not None
    db_session.add(UserRole(membership_id=membership.membership_id, role_id=role.role_id))
    db_session.flush()


def create_ownership(
    client: TestClient,
    user: User,
    society_id,
    unit_id,
    person_id,
    start_date: str,
    *,
    share_percentage: str | None = "100",
    end_date: str | None = None,
):
    body = {
        "unit_id": str(unit_id),
        "person_id": str(person_id),
        "ownership_type": "FREEHOLD",
        "share_percentage": share_percentage,
        "start_date": start_date,
        "end_date": end_date,
    }
    return client.post(
        f"/api/v1/ownerships/societies/{society_id}",
        headers=bearer_headers(user),
        json=body,
    )


def test_ownership_api_shared_ownership_and_overlap_conflict(
    client: TestClient,
    db_session: Session,
    ownership_tenant_data: dict[str, object],
) -> None:
    user = ownership_tenant_data["user"]
    society = ownership_tenant_data["society_a"]
    unit = ownership_tenant_data["unit_a"]
    people = ownership_tenant_data["people"]
    grant_property_permissions(
        db_session,
        user,
        society.society_id,
        "property:manage",
        "property:read",
    )

    first = create_ownership(
        client, user, society.society_id, unit.unit_id, people[0].person_id, "2024-01-01",
        share_percentage="60",
    )
    second = create_ownership(
        client, user, society.society_id, unit.unit_id, people[1].person_id, "2024-01-01",
        share_percentage="40",
    )
    conflict = create_ownership(
        client, user, society.society_id, unit.unit_id, people[2].person_id, "2024-01-01",
        share_percentage="1",
    )
    assert first.status_code == second.status_code == 201
    assert Decimal(first.json()["share_percentage"]) + Decimal(
        second.json()["share_percentage"]
    ) == Decimal("100.00")
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == (
        "Active ownership shares for a unit cannot exceed 100% on overlapping dates."
    )
    assert "sql" not in conflict.text.lower()

    listing = client.get(
        f"/api/v1/ownerships/societies/{society.society_id}",
        params={"unit_id": str(unit.unit_id)},
        headers=bearer_headers(user),
    )
    person_listing = client.get(
        f"/api/v1/ownerships/societies/{society.society_id}",
        params={"person_id": str(people[0].person_id)},
        headers=bearer_headers(user),
    )
    assert listing.status_code == 200
    assert len(listing.json()) == 2
    assert len(person_listing.json()) == 1


def test_ownership_api_historical_successor_and_safe_end_update(
    client: TestClient,
    db_session: Session,
    ownership_tenant_data: dict[str, object],
) -> None:
    user = ownership_tenant_data["user"]
    society = ownership_tenant_data["society_a"]
    unit = ownership_tenant_data["unit_a"]
    person = ownership_tenant_data["people"][0]
    grant_property_permissions(
        db_session, user, society.society_id, "property:manage", "property:read"
    )

    previous = create_ownership(
        client,
        user,
        society.society_id,
        unit.unit_id,
        person.person_id,
        "2024-01-01",
        end_date="2024-12-31",
    )
    successor = create_ownership(
        client,
        user,
        society.society_id,
        unit.unit_id,
        person.person_id,
        "2025-01-01",
    )
    assert previous.status_code == successor.status_code == 201
    assert previous.json()["status"] == "INACTIVE"
    assert successor.json()["status"] == "ACTIVE"

    record_id = successor.json()["ownership_id"]
    invalid_end = client.patch(
        f"/api/v1/ownerships/societies/{society.society_id}/{record_id}",
        headers=bearer_headers(user),
        json={"end_date": "2024-12-31"},
    )
    assert invalid_end.status_code == 400
    ended = client.patch(
        f"/api/v1/ownerships/societies/{society.society_id}/{record_id}",
        headers=bearer_headers(user),
        json={"end_date": "2025-12-31"},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "INACTIVE"
    assert ended.json()["person_id"] == str(person.person_id)
    assert ended.json()["start_date"] == "2025-01-01"

    audit_rows = db_session.scalars(
        select(AuditLog).where(
            AuditLog.society_id == society.society_id,
            AuditLog.entity_id == record_id,
        )
    ).all()
    assert any(
        row.action == "ownership_updated" and row.actor_user_id == user.user_id
        for row in audit_rows
    )


def test_ownership_api_transfer_is_atomic_and_audited(
    client: TestClient,
    db_session: Session,
    ownership_tenant_data: dict[str, object],
) -> None:
    user = ownership_tenant_data["user"]
    society = ownership_tenant_data["society_a"]
    unit = ownership_tenant_data["unit_a"]
    people = ownership_tenant_data["people"]
    grant_property_permissions(
        db_session, user, society.society_id, "property:manage", "property:read"
    )
    original = create_ownership(
        client, user, society.society_id, unit.unit_id, people[0].person_id, "2024-01-01"
    )
    assert original.status_code == 201
    source_id = original.json()["ownership_id"]
    transfer_path = (
        f"/api/v1/ownerships/societies/{society.society_id}/"
        f"{source_id}/transfer"
    )
    invalid = client.post(
        transfer_path,
        headers=bearer_headers(user),
        json={
            "receiving_person_id": str(people[1].person_id),
            "transfer_date": "2024-01-01",
        },
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == (
        "transfer_date must be after the ownership start_date."
    )

    transferred = client.post(
        transfer_path,
        headers=bearer_headers(user),
        json={
            "receiving_person_id": str(people[1].person_id),
            "transfer_date": "2025-01-01",
        },
    )
    assert transferred.status_code == 200
    previous = transferred.json()["previous_ownership"]
    receiving = transferred.json()["new_ownership"]
    assert previous["ownership_id"] == source_id
    assert previous["end_date"] == "2024-12-31"
    assert previous["status"] == "INACTIVE"
    assert receiving["person_id"] == str(people[1].person_id)
    assert receiving["start_date"] == "2025-01-01"
    assert receiving["share_percentage"] == "100.00"
    assert db_session.scalar(
        select(Ownership.ownership_id).where(
            Ownership.society_id == society.society_id,
            Ownership.ownership_id == source_id,
        )
    ) is not None

    events = db_session.scalars(
        select(AuditLog).where(
            AuditLog.society_id == society.society_id,
            AuditLog.entity_type == "ownership",
            AuditLog.entity_id.in_([source_id, receiving["ownership_id"]]),
        )
    ).all()
    assert {(event.action, event.actor_user_id) for event in events} == {
        ("ownership_transferred_out", user.user_id),
        ("ownership_transferred_in", user.user_id),
        ("ownership_created", user.user_id),
    }


def test_ownership_api_tenant_and_permission_denials(
    client: TestClient,
    db_session: Session,
    ownership_tenant_data: dict[str, object],
) -> None:
    user = ownership_tenant_data["user"]
    society_a = ownership_tenant_data["society_a"]
    society_b = ownership_tenant_data["society_b"]
    unit_b = ownership_tenant_data["unit_b"]
    people = ownership_tenant_data["people"]
    existing = Ownership(
        society_id=society_b.society_id,
        unit_id=unit_b.unit_id,
        person_id=people[3].person_id,
        share_percentage=Decimal("100"),
        start_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    db_session.add(existing)
    db_session.flush()

    other_society = client.get(
        f"/api/v1/ownerships/societies/{society_b.society_id}/{existing.ownership_id}",
        headers=bearer_headers(user),
    )
    assert other_society.status_code == 403
    assert "not found" not in other_society.text.lower()

    read_denied = client.get(
        f"/api/v1/ownerships/societies/{society_a.society_id}",
        headers=bearer_headers(user),
    )
    manage_denied = create_ownership(
        client,
        user,
        society_a.society_id,
        ownership_tenant_data["unit_a"].unit_id,
        people[0].person_id,
        "2024-01-01",
    )
    assert read_denied.status_code == manage_denied.status_code == 403

    grant_property_permissions(
        db_session, user, society_a.society_id, "property:manage"
    )
    missing_read = client.get(
        f"/api/v1/ownerships/societies/{society_a.society_id}",
        headers=bearer_headers(user),
    )
    allowed_write = create_ownership(
        client,
        user,
        society_a.society_id,
        ownership_tenant_data["unit_a"].unit_id,
        people[0].person_id,
        "2024-01-01",
    )
    assert missing_read.status_code == 403
    assert allowed_write.status_code == 201
