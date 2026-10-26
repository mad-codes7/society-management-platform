from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.history import OccupancyHistory
from app.models.person import Person, Resident
from app.models.property import Building, Floor, Unit
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.society import Society
from app.models.user import SocietyMembership, User
from test_auth_tenancy import bearer_headers


@pytest.fixture
def tenant_data(db_session: Session) -> dict[str, object]:
    suffix = uuid4().hex
    society_a = Society(name=f"Occupancy Tenant A {suffix}", status="ACTIVE")
    society_b = Society(name=f"Occupancy Tenant B {suffix}", status="ACTIVE")
    user = User(
        person=Person(full_name="Occupancy Test User"),
        email=f"occupancy-{suffix}@example.com",
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
        name="Tower A",
        code=f"A-{suffix[:8]}",
        total_floors=1,
    )
    building_b = Building(
        society_id=society_b.society_id,
        name="Tower B",
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
    person_b = Person(full_name="Occupancy Tenant B Resident")
    db_session.add_all([unit_a, unit_b, person_b])
    db_session.flush()
    resident_b = Resident(
        society_id=society_b.society_id,
        unit_id=unit_b.unit_id,
        person_id=person_b.person_id,
    )
    db_session.add(resident_b)
    db_session.flush()

    return {
        "society_a": society_a,
        "society_b": society_b,
        "regular_user": user,
        "unit_a": unit_a,
        "unit_b": unit_b,
        "resident_b": resident_b,
    }


def grant_resident_permissions(
    db_session: Session,
    user: User,
    society_id,
    *codes: str,
) -> None:
    role = Role(
        name=f"Occupancy Test Role {uuid4().hex}",
        code=f"occupancy_test_{uuid4().hex}",
        is_active=True,
    )
    db_session.add(role)
    db_session.flush()

    for code in codes:
        permission = db_session.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, module="residents")
            db_session.add(permission)
            db_session.flush()
        db_session.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))

    membership = db_session.scalar(
        select(SocietyMembership).where(
            SocietyMembership.user_id == user.user_id,
            SocietyMembership.society_id == society_id,
        )
    )
    assert membership is not None
    db_session.add(UserRole(membership_id=membership.membership_id, role_id=role.role_id))
    db_session.flush()


def add_resident_people(
    db_session: Session,
    society_id,
    unit_id,
    count: int,
) -> list[Person]:
    people = [Person(full_name=f"Occupancy Person {uuid4().hex}") for _ in range(count)]
    db_session.add_all(people)
    db_session.flush()
    db_session.add_all(
        [
            Resident(
                society_id=society_id,
                unit_id=unit_id,
                person_id=person.person_id,
                resident_type="TENANT",
                status="ACTIVE",
            )
            for person in people
        ]
    )
    db_session.flush()
    return people


def check_in(
    client: TestClient,
    user: User,
    society_id,
    unit_id,
    person_id,
    move_in_date: str,
):
    return client.post(
        f"/api/v1/occupancies/societies/{society_id}",
        headers=bearer_headers(user),
        json={
            "unit_id": str(unit_id),
            "person_id": str(person_id),
            "occupancy_type": "TENANT",
            "move_in_date": move_in_date,
        },
    )


def test_occupancy_api_household_checkout_and_inclusive_successor(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]
    unit = tenant_data["unit_a"]
    people = add_resident_people(db_session, society.society_id, unit.unit_id, 2)
    grant_resident_permissions(
        db_session,
        user,
        society.society_id,
        "resident:read",
        "resident:manage",
    )

    first = check_in(
        client, user, society.society_id, unit.unit_id, people[0].person_id, "2026-01-01"
    )
    household_member = check_in(
        client, user, society.society_id, unit.unit_id, people[1].person_id, "2026-01-01"
    )
    assert first.status_code == 201
    assert household_member.status_code == 201

    occupancy_id = first.json()["occupancy_id"]
    listing = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}",
        params={"unit_id": str(unit.unit_id)},
        headers=bearer_headers(user),
    )
    person_listing = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}",
        params={"person_id": str(people[0].person_id)},
        headers=bearer_headers(user),
    )
    detail = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}/{occupancy_id}",
        headers=bearer_headers(user),
    )
    assert listing.status_code == 200
    assert {row["person_id"] for row in listing.json()} == {
        str(person.person_id) for person in people
    }
    assert len(person_listing.json()) == 1
    assert detail.status_code == 200
    assert detail.json()["occupancy_id"] == occupancy_id

    overlap = check_in(
        client, user, society.society_id, unit.unit_id, people[0].person_id, "2026-01-15"
    )
    assert overlap.status_code == 409
    assert overlap.json()["detail"] == "Occupancy dates overlap an existing record for this person and unit."

    checkout = client.post(
        f"/api/v1/occupancies/societies/{society.society_id}/{occupancy_id}/check-out",
        headers=bearer_headers(user),
        json={"move_out_date": "2026-01-31"},
    )
    assert checkout.status_code == 200
    assert checkout.json()["status"] == "INACTIVE"
    assert checkout.json()["move_out_date"] == "2026-01-31"

    same_day_successor = check_in(
        client, user, society.society_id, unit.unit_id, people[0].person_id, "2026-01-31"
    )
    next_day_successor = check_in(
        client, user, society.society_id, unit.unit_id, people[0].person_id, "2026-02-01"
    )
    assert same_day_successor.status_code == 409
    assert next_day_successor.status_code == 201

    db_session.refresh(people[0])
    resident = db_session.scalar(
        select(Resident).where(
            Resident.society_id == society.society_id,
            Resident.person_id == people[0].person_id,
        )
    )
    db_session.refresh(unit)
    assert people[0].status == "ACTIVE"
    assert resident is not None and resident.status == "ACTIVE"
    assert unit.occupancy_status == "VACANT"

    events = db_session.scalars(
        select(AuditLog).where(
            AuditLog.society_id == society.society_id,
            AuditLog.entity_type == "occupancy_history",
            AuditLog.entity_id == occupancy_id,
        )
    ).all()
    assert {(event.action, event.actor_user_id) for event in events} == {
        ("occupancy_checked_in", user.user_id),
        ("occupancy_checked_out", user.user_id),
    }
    check_in_event = next(event for event in events if event.action == "occupancy_checked_in")
    check_out_event = next(event for event in events if event.action == "occupancy_checked_out")
    assert check_in_event.after_data == {
        "occupancy_type": "TENANT",
        "move_in_date": "2026-01-01",
    }
    assert check_out_event.before_data == {
        "status": "ACTIVE",
        "move_out_date": None,
    }
    assert check_out_event.after_data == {
        "status": "INACTIVE",
        "move_out_date": "2026-01-31",
    }


def test_occupancy_api_rejects_invalid_dates_with_400(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]
    unit = tenant_data["unit_a"]
    person = add_resident_people(db_session, society.society_id, unit.unit_id, 1)[0]
    grant_resident_permissions(
        db_session, user, society.society_id, "resident:manage"
    )

    invalid_date = check_in(
        client, user, society.society_id, unit.unit_id, person.person_id, "not-a-date"
    )
    assert invalid_date.status_code == 400
    assert invalid_date.json()["detail"] == "move_in_date must be a valid ISO date (YYYY-MM-DD)."

    created = check_in(
        client, user, society.society_id, unit.unit_id, person.person_id, "2026-05-10"
    )
    assert created.status_code == 201
    invalid_checkout = client.post(
        f"/api/v1/occupancies/societies/{society.society_id}/"
        f"{created.json()['occupancy_id']}/check-out",
        headers=bearer_headers(user),
        json={"move_out_date": "2026-05-09"},
    )
    assert invalid_checkout.status_code == 400
    assert invalid_checkout.json()["detail"] == "move_out_date cannot be before move_in_date."
    assert db_session.scalar(
        select(OccupancyHistory.status).where(
            OccupancyHistory.occupancy_id == created.json()["occupancy_id"]
        )
    ) == "ACTIVE"


def test_occupancy_api_checks_tenant_before_record_existence(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_b"]
    resident = tenant_data["resident_b"]
    db_session.add(
        OccupancyHistory(
            society_id=society.society_id,
            unit_id=resident.unit_id,
            person_id=resident.person_id,
            occupancy_type="TENANT",
            move_in_date=date(2026, 1, 1),
            status="ACTIVE",
        )
    )
    db_session.flush()
    occupancy = db_session.scalar(
        select(OccupancyHistory).where(
            OccupancyHistory.society_id == society.society_id,
            OccupancyHistory.person_id == resident.person_id,
        )
    )
    assert occupancy is not None

    listing = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}",
        headers=bearer_headers(user),
    )
    detail = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}/{occupancy.occupancy_id}",
        headers=bearer_headers(user),
    )
    checkin = check_in(
        client,
        user,
        society.society_id,
        resident.unit_id,
        resident.person_id,
        "2027-01-01",
    )
    assert listing.status_code == 403
    assert detail.status_code == 403
    assert checkin.status_code == 403


def test_occupancy_api_requires_read_and_manage_permissions(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]
    unit = tenant_data["unit_a"]
    person = add_resident_people(db_session, society.society_id, unit.unit_id, 1)[0]

    no_permissions_read = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}",
        headers=bearer_headers(user),
    )
    no_permissions_write = check_in(
        client, user, society.society_id, unit.unit_id, person.person_id, "2027-01-01"
    )
    assert no_permissions_read.status_code == 403
    assert no_permissions_write.status_code == 403

    grant_resident_permissions(
        db_session, user, society.society_id, "resident:manage"
    )
    missing_read = client.get(
        f"/api/v1/occupancies/societies/{society.society_id}",
        headers=bearer_headers(user),
    )
    allowed_write = check_in(
        client, user, society.society_id, unit.unit_id, person.person_id, "2027-01-01"
    )
    assert missing_read.status_code == 403
    assert allowed_write.status_code == 201
