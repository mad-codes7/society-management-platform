from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.history import Lease
from app.models.person import Person, Resident
from app.models.property import Building, Floor, Unit
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.society import Society
from app.models.user import SocietyMembership, User
from app.modules.leases.service import lease_service
from test_auth_tenancy import bearer_headers


@pytest.fixture(scope="module")
def engine(alembic_engine):
    return alembic_engine


def test_lease_api_uses_alembic_exclusion_constraint(engine) -> None:
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        constraint = connection.scalar(
            text(
                """
                SELECT pg_get_constraintdef(oid)
                FROM pg_constraint
                WHERE conrelid = 'leases'::regclass
                  AND conname = 'ex_leases_active_unit_dates'
                  AND contype = 'x'
                """
            )
        )

    assert revision == "f1a2b3c4d5e6"
    assert constraint is not None
    assert "unit_id WITH =" in constraint
    assert "daterange(lease_start, COALESCE(lease_end, 'infinity'::date), '[]'::text) WITH &&" in constraint


@pytest.fixture
def lease_tenant_data(db_session: Session) -> dict[str, object]:
    suffix = uuid4().hex
    society_a = Society(name=f"Lease Tenant A {suffix}", status="ACTIVE")
    society_b = Society(name=f"Lease Tenant B {suffix}", status="ACTIVE")
    user = User(
        person=Person(full_name="Lease Test User"),
        email=f"lease-{suffix}@example.com",
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
        name="Lease Tower A",
        code=f"A-{suffix[:8]}",
        total_floors=1,
    )
    building_b = Building(
        society_id=society_b.society_id,
        name="Lease Tower B",
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
    people_a = [
        Person(full_name=f"Lease Person {index} {suffix}")
        for index in range(1, 4)
    ]
    person_b = Person(full_name=f"Other Society Lease Person {suffix}")
    db_session.add_all([unit_a, unit_b, *people_a, person_b])
    db_session.flush()
    db_session.add_all(
        [
            Resident(
                society_id=society_a.society_id,
                unit_id=unit_a.unit_id,
                person_id=person.person_id,
                resident_type="TENANT",
                status="ACTIVE",
            )
            for person in people_a
        ]
        + [
            Resident(
                society_id=society_b.society_id,
                unit_id=unit_b.unit_id,
                person_id=person_b.person_id,
                resident_type="TENANT",
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
        "people_a": people_a,
        "person_b": person_b,
    }


def grant_property_permissions(
    db_session: Session,
    user: User,
    society_id,
    *codes: str,
) -> None:
    role = Role(
        name=f"Lease Test Role {uuid4().hex}",
        code=f"lease_test_{uuid4().hex}",
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


def create_lease(
    client: TestClient,
    user: User,
    society_id,
    unit_id,
    tenant_person_id,
    lease_start: str,
    lease_end: str | None = None,
    owner_person_id=None,
):
    return client.post(
        f"/api/v1/leases/societies/{society_id}",
        headers=bearer_headers(user),
        json={
            "unit_id": str(unit_id),
            "tenant_person_id": str(tenant_person_id),
            "owner_person_id": (
                str(owner_person_id) if owner_person_id is not None else None
            ),
            "lease_start": lease_start,
            "lease_end": lease_end,
        },
    )


def test_lease_api_create_list_detail_and_overlap_conflict(
    client: TestClient,
    db_session: Session,
    lease_tenant_data: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = lease_tenant_data["user"]
    society = lease_tenant_data["society_a"]
    unit = lease_tenant_data["unit_a"]
    tenant, other_tenant, _ = lease_tenant_data["people_a"]
    grant_property_permissions(
        db_session,
        user,
        society.society_id,
        "property:manage",
        "property:read",
    )

    created = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        tenant.person_id,
        "2027-01-01",
        "2027-06-30",
        other_tenant.person_id,
    )
    conflict = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        other_tenant.person_id,
        "2027-06-30",
        "2027-12-31",
    )
    assert created.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == (
        "Lease dates overlap an existing lease for this unit."
    )
    assert "sql" not in conflict.text.lower()
    assert "constraint" not in conflict.text.lower()

    monkeypatch.setattr(
        lease_service.repository,
        "has_overlapping_lease",
        lambda *args, **kwargs: False,
    )
    database_conflict = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        other_tenant.person_id,
        "2027-06-30",
        "2027-12-31",
    )
    assert database_conflict.status_code == 409
    assert database_conflict.json()["detail"] == (
        "Lease dates overlap an existing lease for this unit."
    )
    assert "sql" not in database_conflict.text.lower()

    listing = client.get(
        f"/api/v1/leases/societies/{society.society_id}",
        params={"unit_id": str(unit.unit_id)},
        headers=bearer_headers(user),
    )
    tenant_listing = client.get(
        f"/api/v1/leases/societies/{society.society_id}",
        params={"tenant_person_id": str(tenant.person_id)},
        headers=bearer_headers(user),
    )
    detail = client.get(
        f"/api/v1/leases/societies/{society.society_id}/{created.json()['lease_id']}",
        headers=bearer_headers(user),
    )
    assert listing.status_code == 200
    assert len(listing.json()) == len(tenant_listing.json()) == 1
    assert detail.status_code == 200
    assert detail.json()["owner_person_id"] == str(other_tenant.person_id)


def test_lease_api_inclusive_successor_and_end_update(
    client: TestClient,
    db_session: Session,
    lease_tenant_data: dict[str, object],
) -> None:
    user = lease_tenant_data["user"]
    society = lease_tenant_data["society_a"]
    unit = lease_tenant_data["unit_a"]
    first_tenant, second_tenant, owner = lease_tenant_data["people_a"]
    grant_property_permissions(
        db_session,
        user,
        society.society_id,
        "property:manage",
        "property:read",
    )

    first = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        first_tenant.person_id,
        "2027-01-01",
        "2027-01-31",
    )
    assert first.status_code == 201
    first_id = first.json()["lease_id"]
    same_day = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        second_tenant.person_id,
        "2027-01-31",
    )
    successor = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        second_tenant.person_id,
        "2027-02-01",
    )
    assert same_day.status_code == 409
    assert successor.status_code == 201

    cannot_clear_end = client.patch(
        f"/api/v1/leases/societies/{society.society_id}/{first_id}",
        headers=bearer_headers(user),
        json={"lease_end": None},
    )
    assert cannot_clear_end.status_code == 409
    assert cannot_clear_end.json()["detail"] == (
        "Lease dates overlap an existing lease for this unit."
    )
    invalid_end = client.post(
        f"/api/v1/leases/societies/{society.society_id}/"
        f"{successor.json()['lease_id']}/end",
        headers=bearer_headers(user),
        json={"lease_end": "2027-01-31"},
    )
    assert invalid_end.status_code == 400
    assert invalid_end.json()["detail"] == "lease_end cannot be before lease_start."
    ended = client.post(
        f"/api/v1/leases/societies/{society.society_id}/"
        f"{successor.json()['lease_id']}/end",
        headers=bearer_headers(user),
        json={"lease_end": "2027-03-01"},
    )
    assert ended.status_code == 200
    assert ended.json()["lease_end"] == "2027-03-01"
    assert ended.json()["status"] == "ACTIVE"

    updated = client.patch(
        f"/api/v1/leases/societies/{society.society_id}/"
        f"{successor.json()['lease_id']}",
        headers=bearer_headers(user),
        json={"owner_person_id": str(owner.person_id)},
    )
    assert updated.status_code == 200
    assert updated.json()["owner_person_id"] == str(owner.person_id)
    assert updated.json()["lease_start"] == "2027-02-01"
    history = client.get(
        f"/api/v1/leases/societies/{society.society_id}",
        params={"unit_id": str(unit.unit_id)},
        headers=bearer_headers(user),
    )
    assert history.status_code == 200
    assert len(history.json()) == 2

    events = db_session.scalars(
        select(AuditLog).where(
            AuditLog.society_id == society.society_id,
            AuditLog.entity_type == "lease",
        )
    ).all()
    assert any(event.action == "lease_created" for event in events)
    assert any(event.action == "lease_terminated" for event in events)
    assert any(event.action == "lease_updated" for event in events)
    assert all(event.actor_user_id == user.user_id for event in events)


def test_lease_api_invalid_dates_and_tenant_scoping(
    client: TestClient,
    db_session: Session,
    lease_tenant_data: dict[str, object],
) -> None:
    user = lease_tenant_data["user"]
    society_a = lease_tenant_data["society_a"]
    society_b = lease_tenant_data["society_b"]
    unit_a = lease_tenant_data["unit_a"]
    unit_b = lease_tenant_data["unit_b"]
    tenant = lease_tenant_data["people_a"][0]
    person_b = lease_tenant_data["person_b"]
    grant_property_permissions(
        db_session,
        user,
        society_a.society_id,
        "property:manage",
        "property:read",
    )

    invalid = create_lease(
        client,
        user,
        society_a.society_id,
        unit_a.unit_id,
        tenant.person_id,
        "2027-02-01",
        "2027-01-31",
    )
    assert invalid.status_code == 400
    assert invalid.json()["detail"] == "lease_end cannot be before lease_start."

    other_lease = Lease(
        society_id=society_b.society_id,
        unit_id=unit_b.unit_id,
        tenant_person_id=person_b.person_id,
        lease_start=date(2027, 1, 1),
        status="ACTIVE",
    )
    db_session.add(other_lease)
    db_session.flush()
    denied = client.get(
        f"/api/v1/leases/societies/{society_b.society_id}/{other_lease.lease_id}",
        headers=bearer_headers(user),
    )
    assert denied.status_code == 403
    assert "not found" not in denied.text.lower()


def test_lease_api_requires_read_and_manage_permissions(
    client: TestClient,
    db_session: Session,
    lease_tenant_data: dict[str, object],
) -> None:
    user = lease_tenant_data["user"]
    society = lease_tenant_data["society_a"]
    unit = lease_tenant_data["unit_a"]
    tenant = lease_tenant_data["people_a"][0]

    read_denied = client.get(
        f"/api/v1/leases/societies/{society.society_id}",
        headers=bearer_headers(user),
    )
    manage_denied = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        tenant.person_id,
        "2027-01-01",
    )
    assert read_denied.status_code == manage_denied.status_code == 403

    grant_property_permissions(
        db_session, user, society.society_id, "property:manage"
    )
    missing_read = client.get(
        f"/api/v1/leases/societies/{society.society_id}",
        headers=bearer_headers(user),
    )
    created = create_lease(
        client,
        user,
        society.society_id,
        unit.unit_id,
        tenant.person_id,
        "2027-01-01",
    )
    assert missing_read.status_code == 403
    assert created.status_code == 201
