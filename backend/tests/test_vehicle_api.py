from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.history import Vehicle
from app.models.person import Person, Resident
from app.models.property import Building, Floor, Unit
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.society import Society
from app.models.user import SocietyMembership, User
from test_auth_tenancy import bearer_headers


@pytest.fixture
def vehicle_tenant_data(migrated_db_session: Session) -> dict[str, object]:
    suffix = uuid4().hex
    society_a = Society(name=f"Vehicle Society A {suffix}", status="ACTIVE")
    society_b = Society(name=f"Vehicle Society B {suffix}", status="ACTIVE")
    user = User(
        person=Person(full_name="Vehicle Test User"),
        email=f"vehicle-{suffix}@example.com",
        password_hash=hash_password("Test-Only-Password-1!"),
        is_active=True,
    )
    db = migrated_db_session
    db.add_all([society_a, society_b, user])
    db.flush()
    membership = SocietyMembership(
        user_id=user.user_id,
        society_id=society_a.society_id,
        status="ACTIVE",
    )
    db.add(membership)

    building_a = Building(
        society_id=society_a.society_id,
        name="Vehicle Tower A",
        code=f"A-{suffix[:8]}",
        total_floors=1,
    )
    building_b = Building(
        society_id=society_b.society_id,
        name="Vehicle Tower B",
        code=f"B-{suffix[:8]}",
        total_floors=1,
    )
    db.add_all([building_a, building_b])
    db.flush()
    floor_a = Floor(building_id=building_a.building_id, floor_number=1)
    floor_b = Floor(building_id=building_b.building_id, floor_number=1)
    db.add_all([floor_a, floor_b])
    db.flush()

    unit_a = Unit(
        society_id=society_a.society_id,
        building_id=building_a.building_id,
        floor_id=floor_a.floor_id,
        unit_number="A-101",
    )
    unit_a2 = Unit(
        society_id=society_a.society_id,
        building_id=building_a.building_id,
        floor_id=floor_a.floor_id,
        unit_number="A-102",
    )
    unit_b = Unit(
        society_id=society_b.society_id,
        building_id=building_b.building_id,
        floor_id=floor_b.floor_id,
        unit_number="B-101",
    )
    person_a = Person(full_name=f"Resident A {suffix}")
    person_a2 = Person(full_name=f"Resident A2 {suffix}")
    person_b = Person(full_name=f"Resident B {suffix}")
    db.add_all([unit_a, unit_a2, unit_b, person_a, person_a2, person_b])
    db.flush()
    resident_a = Resident(
        society_id=society_a.society_id,
        unit_id=unit_a.unit_id,
        person_id=person_a.person_id,
        status="ACTIVE",
    )
    resident_a2 = Resident(
        society_id=society_a.society_id,
        unit_id=unit_a2.unit_id,
        person_id=person_a2.person_id,
        status="ACTIVE",
    )
    resident_b = Resident(
        society_id=society_b.society_id,
        unit_id=unit_b.unit_id,
        person_id=person_b.person_id,
        status="ACTIVE",
    )
    db.add_all([resident_a, resident_a2, resident_b])
    db.flush()
    return {
        "society_a": society_a,
        "society_b": society_b,
        "user": user,
        "membership": membership,
        "unit_a": unit_a,
        "unit_a2": unit_a2,
        "unit_b": unit_b,
        "person_a": person_a,
        "person_a2": person_a2,
        "person_b": person_b,
    }


def grant_property_permissions(
    db: Session,
    user: User,
    membership: SocietyMembership,
    *codes: str,
) -> None:
    role = Role(
        name=f"Vehicle Test Role {uuid4().hex}",
        code=f"vehicle_test_{uuid4().hex}",
        is_active=True,
    )
    db.add(role)
    db.flush()
    for code in codes:
        permission = db.scalar(select(Permission).where(Permission.code == code))
        if permission is None:
            permission = Permission(code=code, module="property")
            db.add(permission)
            db.flush()
        db.add(RolePermission(role_id=role.role_id, permission_id=permission.permission_id))
    db.add(UserRole(membership_id=membership.membership_id, role_id=role.role_id))
    db.flush()


def register_vehicle(
    client: TestClient,
    user: User,
    society_id,
    registration_number: str,
    *,
    vehicle_type: str = "CAR",
    person_id=None,
    unit_id=None,
    make_model: str | None = None,
    colour: str | None = None,
):
    return client.post(
        f"/api/v1/vehicles/societies/{society_id}",
        headers=bearer_headers(user),
        json={
            "registration_number": registration_number,
            "vehicle_type": vehicle_type,
            "person_id": str(person_id) if person_id else None,
            "unit_id": str(unit_id) if unit_id else None,
            "make_model": make_model,
            "colour": colour,
        },
    )


def test_vehicle_api_register_duplicate_and_list_detail(
    migrated_client: TestClient,
    migrated_db_session: Session,
    vehicle_tenant_data: dict[str, object],
) -> None:
    client = migrated_client
    db = migrated_db_session
    user = vehicle_tenant_data["user"]
    society = vehicle_tenant_data["society_a"]
    unit = vehicle_tenant_data["unit_a"]
    person = vehicle_tenant_data["person_a"]
    grant_property_permissions(
        db,
        user,
        vehicle_tenant_data["membership"],
        "property:manage",
        "property:read",
    )

    created = register_vehicle(
        client,
        user,
        society.society_id,
        " custom registration ",
        person_id=person.person_id,
        unit_id=unit.unit_id,
        make_model="Model X",
        colour="Blue",
    )
    assert created.status_code == 201
    assert created.json()["registration_number"] == " custom registration "
    assert created.json()["person_id"] == str(person.person_id)
    assert created.json()["unit_id"] == str(unit.unit_id)
    duplicate = register_vehicle(
        client,
        user,
        society.society_id,
        " custom registration ",
        vehicle_type="BIKE",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == (
        "A vehicle with this registration number is already registered in this society."
    )
    assert "sql" not in duplicate.text.lower()
    assert "uq_vehicles" not in duplicate.text.lower()

    by_unit = client.get(
        f"/api/v1/vehicles/societies/{society.society_id}",
        params={"unit_id": str(unit.unit_id)},
        headers=bearer_headers(user),
    )
    by_person = client.get(
        f"/api/v1/vehicles/societies/{society.society_id}",
        params={"person_id": str(person.person_id), "status": "ACTIVE"},
        headers=bearer_headers(user),
    )
    detail = client.get(
        f"/api/v1/vehicles/societies/{society.society_id}/{created.json()['vehicle_id']}",
        headers=bearer_headers(user),
    )
    assert by_unit.status_code == by_person.status_code == detail.status_code == 200
    assert len(by_unit.json()) == len(by_person.json()) == 1
    assert detail.json()["vehicle_id"] == created.json()["vehicle_id"]


def test_vehicle_api_validates_associations_and_updates(
    migrated_client: TestClient,
    migrated_db_session: Session,
    vehicle_tenant_data: dict[str, object],
) -> None:
    client = migrated_client
    db = migrated_db_session
    user = vehicle_tenant_data["user"]
    society = vehicle_tenant_data["society_a"]
    grant_property_permissions(
        db, user, vehicle_tenant_data["membership"], "property:manage"
    )

    invalid_pair = register_vehicle(
        client,
        user,
        society.society_id,
        "PAIR-001",
        person_id=vehicle_tenant_data["person_a"].person_id,
        unit_id=vehicle_tenant_data["unit_a2"].unit_id,
    )
    foreign_person = register_vehicle(
        client,
        user,
        society.society_id,
        "FOREIGN-001",
        person_id=vehicle_tenant_data["person_b"].person_id,
    )
    foreign_unit = register_vehicle(
        client,
        user,
        society.society_id,
        "FOREIGN-002",
        unit_id=vehicle_tenant_data["unit_b"].unit_id,
    )
    assert invalid_pair.status_code == 400
    assert foreign_person.status_code == foreign_unit.status_code == 404

    created = register_vehicle(
        client,
        user,
        society.society_id,
        "UPDATE-001",
        person_id=vehicle_tenant_data["person_a"].person_id,
        unit_id=vehicle_tenant_data["unit_a"].unit_id,
    )
    assert created.status_code == 201
    vehicle_id = created.json()["vehicle_id"]
    updated = client.patch(
        f"/api/v1/vehicles/societies/{society.society_id}/{vehicle_id}",
        headers=bearer_headers(user),
        json={
            "person_id": str(vehicle_tenant_data["person_a2"].person_id),
            "unit_id": str(vehicle_tenant_data["unit_a2"].unit_id),
            "colour": "Green",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["person_id"] == str(vehicle_tenant_data["person_a2"].person_id)
    assert updated.json()["unit_id"] == str(vehicle_tenant_data["unit_a2"].unit_id)
    assert updated.json()["colour"] == "Green"

    rejected_update = client.patch(
        f"/api/v1/vehicles/societies/{society.society_id}/{vehicle_id}",
        headers=bearer_headers(user),
        json={"unit_id": str(vehicle_tenant_data["unit_a"].unit_id)},
    )
    assert rejected_update.status_code == 400
    assert rejected_update.json()["detail"] == (
        "Person must be an active resident of the specified unit."
    )
    db.expire_all()
    persisted = db.scalar(select(Vehicle).where(Vehicle.vehicle_id == vehicle_id))
    assert persisted is not None and persisted.unit_id == vehicle_tenant_data["unit_a2"].unit_id


def test_vehicle_api_deactivation_history_and_audit(
    migrated_client: TestClient,
    migrated_db_session: Session,
    vehicle_tenant_data: dict[str, object],
) -> None:
    client = migrated_client
    db = migrated_db_session
    user = vehicle_tenant_data["user"]
    society = vehicle_tenant_data["society_a"]
    grant_property_permissions(
        db,
        user,
        vehicle_tenant_data["membership"],
        "property:manage",
        "property:read",
    )
    created = register_vehicle(
        client,
        user,
        society.society_id,
        "DEACTIVATE-001",
        person_id=vehicle_tenant_data["person_a"].person_id,
        unit_id=vehicle_tenant_data["unit_a"].unit_id,
    )
    vehicle_id = created.json()["vehicle_id"]
    deactivated = client.post(
        f"/api/v1/vehicles/societies/{society.society_id}/{vehicle_id}/deactivate",
        headers=bearer_headers(user),
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "INACTIVE"

    inactive_list = client.get(
        f"/api/v1/vehicles/societies/{society.society_id}",
        params={"status": "INACTIVE"},
        headers=bearer_headers(user),
    )
    active_list = client.get(
        f"/api/v1/vehicles/societies/{society.society_id}",
        params={"status": "ACTIVE"},
        headers=bearer_headers(user),
    )
    detail = client.get(
        f"/api/v1/vehicles/societies/{society.society_id}/{vehicle_id}",
        headers=bearer_headers(user),
    )
    assert len(inactive_list.json()) == 1
    assert all(row["vehicle_id"] != vehicle_id for row in active_list.json())
    assert detail.json()["status"] == "INACTIVE"
    assert db.scalar(select(Vehicle.vehicle_id).where(Vehicle.vehicle_id == vehicle_id)) is not None

    logs = db.scalars(
        select(AuditLog).where(
            AuditLog.society_id == society.society_id,
            AuditLog.entity_type == "vehicle",
            AuditLog.entity_id == vehicle_id,
        )
    ).all()
    assert {(log.action, log.actor_user_id) for log in logs} == {
        ("vehicle_registered", user.user_id),
        ("vehicle_deactivated", user.user_id),
    }
    deactivation = next(log for log in logs if log.action == "vehicle_deactivated")
    assert deactivation.before_data["status"] == "ACTIVE"
    assert deactivation.after_data["status"] == "INACTIVE"


def test_vehicle_api_cross_society_and_permission_denials(
    migrated_client: TestClient,
    migrated_db_session: Session,
    vehicle_tenant_data: dict[str, object],
) -> None:
    client = migrated_client
    db = migrated_db_session
    user = vehicle_tenant_data["user"]
    society_a = vehicle_tenant_data["society_a"]
    society_b = vehicle_tenant_data["society_b"]
    vehicle = Vehicle(
        society_id=society_b.society_id,
        person_id=vehicle_tenant_data["person_b"].person_id,
        unit_id=vehicle_tenant_data["unit_b"].unit_id,
        registration_number="PRIVATE-001",
        vehicle_type="CAR",
        status="ACTIVE",
    )
    db.add(vehicle)
    db.flush()
    cross_society = client.get(
        f"/api/v1/vehicles/societies/{society_b.society_id}/{vehicle.vehicle_id}",
        headers=bearer_headers(user),
    )
    assert cross_society.status_code == 403
    assert "not found" not in cross_society.text.lower()

    no_read = client.get(
        f"/api/v1/vehicles/societies/{society_a.society_id}",
        headers=bearer_headers(user),
    )
    no_manage = register_vehicle(
        client, user, society_a.society_id, "DENIED-001"
    )
    assert no_read.status_code == no_manage.status_code == 403

    grant_property_permissions(
        db, user, vehicle_tenant_data["membership"], "property:manage"
    )
    missing_read = client.get(
        f"/api/v1/vehicles/societies/{society_a.society_id}",
        headers=bearer_headers(user),
    )
    allowed_write = register_vehicle(
        client, user, society_a.society_id, "ALLOWED-001"
    )
    assert missing_read.status_code == 403
    assert allowed_write.status_code == 201
