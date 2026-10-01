from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.rbac import Permission, Role, RolePermission, UserRole

from app.core.security import (
    MIN_PASSWORD_LENGTH,
    create_access_token,
    decode_access_token,
    hash_password,
)
from app.models.person import Person, Resident
from app.models.property import Building, Floor, Unit
from app.models.society import Society
from app.models.user import SocietyMembership, User
from app.modules.auth.schemas import SocietyAdminCreateRequest

PASSWORD = "Test-Only-Password-1!"


@pytest.fixture
def tenant_data(db_session: Session) -> dict[str, object]:
    suffix = uuid4().hex
    society_a = Society(name=f"Auth Tenant A {suffix}", status="ACTIVE")
    society_b = Society(name=f"Auth Tenant B {suffix}", status="ACTIVE")
    regular_user = User(
        email=f"regular-{suffix}@example.com",
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    inactive_membership_user = User(
        email=f"inactive-member-{suffix}@example.com",
        password_hash=hash_password(PASSWORD),
        is_active=True,
    )
    inactive_user = User(
        email=f"inactive-user-{suffix}@example.com",
        password_hash=hash_password(PASSWORD),
        is_active=False,
    )
    super_admin = User(
        email=f"super-admin-{suffix}@example.com",
        password_hash=hash_password(PASSWORD),
        is_active=True,
        is_super_admin=True,
    )
    db_session.add_all(
        [society_a, society_b, regular_user, inactive_membership_user, inactive_user, super_admin]
    )
    db_session.flush()

    db_session.add_all(
        [
            SocietyMembership(
                user_id=regular_user.user_id,
                society_id=society_a.society_id,
                status="ACTIVE",
            ),
            SocietyMembership(
                user_id=inactive_membership_user.user_id,
                society_id=society_b.society_id,
                status="INACTIVE",
            ),
        ]
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
    person_b = Person(first_name="Test", last_name="Resident")
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
        "regular_user": regular_user,
        "inactive_membership_user": inactive_membership_user,
        "inactive_user": inactive_user,
        "super_admin": super_admin,
        "building_a": building_a,
        "building_b": building_b,
        "unit_b": unit_b,
        "resident_b": resident_b,
    }


def bearer_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.user_id))}"}


def create_society_admin(
    client: TestClient,
    super_admin: User,
) -> tuple[object, str]:
    suffix = uuid4().hex
    initial_password = f"Initial-{suffix}!"
    response = client.post(
        "/api/v1/auth/society-admins",
        headers=bearer_headers(super_admin),
        json={
            "first_name": "Society",
            "last_name": "Admin",
            "email": f"society-admin-{suffix}@example.com",
            "initial_password": initial_password,
        },
    )
    return response, initial_password


def test_valid_login_returns_bearer_access_token(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )

    assert response.status_code == 200
    token_response = response.json()
    assert token_response["token_type"] == "bearer"
    assert token_response["access_token"]
    assert token_response["expires_in"] > 0
    claims = decode_access_token(token_response["access_token"])
    assert claims["sub"] == str(user.user_id)
    assert claims["token_type"] == "access"


def test_wrong_password_returns_401(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_inactive_user_login_returns_403(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["inactive_user"]
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": PASSWORD},
    )

    assert response.status_code == 403


def test_me_requires_token_and_accepts_valid_token(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    no_token = client.get("/api/v1/auth/me")
    user = tenant_data["regular_user"]
    authenticated = client.get("/api/v1/auth/me", headers=bearer_headers(user))

    assert no_token.status_code == 401
    assert no_token.headers["www-authenticate"] == "Bearer"
    assert authenticated.status_code == 200
    assert authenticated.json()["user_id"] == str(user.user_id)
    assert "password_hash" not in authenticated.json()


def test_member_can_access_society_a_protected_data(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society_a = tenant_data["society_a"]

    permission = Permission(
        code="society:read",
        description="View society information.",
        module="society",
    )
    role = Role(
        name=f"Test Society Reader {uuid4().hex}",
        description="Test role with society read access.",
        is_active=True,
    )

    db_session.add_all([permission, role])
    db_session.flush()

    db_session.add(
        RolePermission(
            role_id=role.role_id,
            permission_id=permission.permission_id,
        )
    )

    membership = (
        db_session.query(SocietyMembership)
        .filter(
            SocietyMembership.user_id == user.user_id,
            SocietyMembership.society_id == society_a.society_id,
        )
        .one()
    )

    db_session.add(
        UserRole(
            membership_id=membership.membership_id,
            role_id=role.role_id,
        )
    )

    db_session.flush()

    response = client.get(
        f"/api/v1/properties/societies/{society_a.society_id}/buildings",
        headers=bearer_headers(user),
    )

    assert response.status_code == 200
    assert [building["building_id"] for building in response.json()] == [
        str(tenant_data["building_a"].building_id)
    ]


def test_member_is_denied_society_b_data(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society_b = tenant_data["society_b"]

    response = client.get(
        f"/api/v1/properties/societies/{society_b.society_id}/buildings",
        headers=bearer_headers(user),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Not authorized to access this society."


def test_inactive_membership_is_denied(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["inactive_membership_user"]
    society_b = tenant_data["society_b"]

    response = client.get(
        f"/api/v1/properties/societies/{society_b.society_id}/buildings",
        headers=bearer_headers(user),
    )

    assert response.status_code == 403


def test_super_admin_can_access_society_management(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["super_admin"]
    society_a = tenant_data["society_a"]

    listing = client.get("/api/v1/societies", headers=bearer_headers(user))
    detail = client.get(
        f"/api/v1/societies/{society_a.society_id}",
        headers=bearer_headers(user),
    )

    assert listing.status_code == 200
    assert detail.status_code == 200
    assert detail.json()["society_id"] == str(society_a.society_id)


def test_regular_user_is_denied_society_management(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]

    listing = client.get("/api/v1/societies", headers=bearer_headers(user))
    creation = client.post(
        "/api/v1/societies",
        headers=bearer_headers(user),
        json={"name": f"Forbidden {uuid4().hex}"},
    )

    assert listing.status_code == 403
    assert creation.status_code == 403


def test_object_id_routes_check_tenant_before_returning_or_mutating(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    building_b = tenant_data["building_b"]
    unit_b = tenant_data["unit_b"]
    resident_b = tenant_data["resident_b"]

    floors = client.get(
        f"/api/v1/properties/buildings/{building_b.building_id}/floors",
        headers=bearer_headers(user),
    )
    unit_update = client.patch(
        f"/api/v1/properties/units/{unit_b.unit_id}",
        headers=bearer_headers(user),
        json={"occupancy_status": "OCCUPIED"},
    )
    resident_detail = client.get(
        f"/api/v1/residents/{resident_b.resident_id}",
        headers=bearer_headers(user),
    )

    assert floors.status_code == 403
    assert unit_update.status_code == 403
    assert resident_detail.status_code == 403


def test_body_society_ids_are_validated_before_create(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    user = tenant_data["regular_user"]
    society_b = tenant_data["society_b"]
    building_b = tenant_data["building_b"]

    building = client.post(
        "/api/v1/properties/buildings",
        headers=bearer_headers(user),
        json={
            "society_id": str(society_b.society_id),
            "name": "Untrusted Tower",
            "code": f"X-{uuid4().hex[:8]}",
        },
    )
    unit_type = client.post(
        "/api/v1/properties/unit-types",
        headers=bearer_headers(user),
        json={"society_id": str(society_b.society_id), "name": "Untrusted Type"},
    )
    unit = client.post(
        "/api/v1/properties/units",
        headers=bearer_headers(user),
        json={
            "society_id": str(society_b.society_id),
            "building_id": str(building_b.building_id),
            "floor_id": str(tenant_data["unit_b"].floor_id),
            "unit_number": "X-999",
        },
    )
    resident = client.post(
        "/api/v1/residents",
        headers=bearer_headers(user),
        json={
            "society_id": str(society_b.society_id),
            "unit_id": str(tenant_data["unit_b"].unit_id),
            "person": {"first_name": "Untrusted", "last_name": "Resident"},
        },
    )

    assert building.status_code == 403
    assert unit_type.status_code == 403
    assert unit.status_code == 403
    assert resident.status_code == 403


def test_super_admin_creates_linked_society_admin_without_secrets(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    super_admin = tenant_data["super_admin"]
    response, initial_password = create_society_admin(client, super_admin)

    assert response.status_code == 201
    body = response.json()
    assert "initial_password" not in body
    assert "password_hash" not in body
    assert body["is_active"] is True
    assert body["is_super_admin"] is False
    assert body["person"]["email"] == body["email"]

    created_user = db_session.get(User, UUID(body["user_id"]))
    assert created_user is not None
    assert created_user.person_id is not None
    created_person = db_session.get(Person, created_user.person_id)
    assert created_person is not None
    assert created_person.email == body["email"]

    login = client.post(
        "/api/v1/auth/login",
        json={"email": body["email"], "password": initial_password},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]


def test_regular_user_cannot_create_society_admin(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    regular_user = tenant_data["regular_user"]
    suffix = uuid4().hex

    response = client.post(
        "/api/v1/auth/society-admins",
        headers=bearer_headers(regular_user),
        json={
            "first_name": "Forbidden",
            "last_name": "Admin",
            "email": f"forbidden-admin-{suffix}@example.com",
            "initial_password": "Test-Only-Initial-Password!",
        },
    )

    assert response.status_code == 403


def test_super_admin_assigns_active_membership(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    super_admin = tenant_data["super_admin"]
    user = tenant_data["regular_user"]
    society_b = tenant_data["society_b"]

    response = client.post(
        f"/api/v1/auth/users/{user.user_id}/memberships",
        headers=bearer_headers(super_admin),
        json={"society_id": str(society_b.society_id)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(user.user_id)
    assert body["society_id"] == str(society_b.society_id)
    assert body["status"] == "ACTIVE"
    assert body["membership_id"]
    assert body["created_at"]
    assert body["updated_at"]


def test_duplicate_membership_returns_409(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    super_admin = tenant_data["super_admin"]
    user = tenant_data["regular_user"]
    society_a = tenant_data["society_a"]

    response = client.post(
        f"/api/v1/auth/users/{user.user_id}/memberships",
        headers=bearer_headers(super_admin),
        json={"society_id": str(society_a.society_id)},
    )

    assert response.status_code == 409


def test_regular_user_cannot_assign_membership(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    regular_user = tenant_data["regular_user"]
    target_user = tenant_data["inactive_membership_user"]
    society_b = tenant_data["society_b"]

    response = client.post(
        f"/api/v1/auth/users/{target_user.user_id}/memberships",
        headers=bearer_headers(regular_user),
        json={"society_id": str(society_b.society_id)},
    )

    assert response.status_code == 403


def test_assigned_admin_can_access_only_the_assigned_society(
    client: TestClient,
    db_session: Session,
    tenant_data: dict[str, object],
) -> None:
    super_admin = tenant_data["super_admin"]
    society_a = tenant_data["society_a"]
    society_b = tenant_data["society_b"]
    creation, initial_password = create_society_admin(client, super_admin)
    assert creation.status_code == 201

    new_user_id = UUID(creation.json()["user_id"])
    assignment = client.post(
        f"/api/v1/auth/users/{new_user_id}/memberships",
        headers=bearer_headers(super_admin),
        json={"society_id": str(society_a.society_id)},
    )
    assert assignment.status_code == 201

    permission = db_session.query(Permission).filter(
        Permission.code == "society:read"
    ).first()

    if permission is None:
        permission = Permission(
            code="society:read",
            description="View society information.",
            module="society",
        )
        db_session.add(permission)
        db_session.flush()

    role = Role(
        name=f"Test Society Admin {uuid4().hex}",
        description="Test Society Admin role.",
        is_active=True,
    )
    db_session.add(role)
    db_session.flush()

    db_session.add(
        RolePermission(
            role_id=role.role_id,
            permission_id=permission.permission_id,
        )
    )

    membership = (
        db_session.query(SocietyMembership)
        .filter(
            SocietyMembership.user_id == new_user_id,
            SocietyMembership.society_id == society_a.society_id,
        )
        .one()
    )

    db_session.add(
        UserRole(
            membership_id=membership.membership_id,
            role_id=role.role_id,
        )
    )

    db_session.flush()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": creation.json()["email"],
            "password": initial_password,
        },
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    society_a_data = client.get(
        f"/api/v1/properties/societies/{society_a.society_id}/buildings",
        headers=headers,
    )
    society_b_data = client.get(
        f"/api/v1/properties/societies/{society_b.society_id}/buildings",
        headers=headers,
    )

    assert society_a_data.status_code == 200
    assert society_b_data.status_code == 403


def test_society_admin_password_uses_shared_minimum() -> None:
    assert MIN_PASSWORD_LENGTH == 12
    with pytest.raises(ValueError):
        SocietyAdminCreateRequest(
            first_name="Short",
            last_name="Password",
            email="short-password@example.com",
            initial_password="too-short",
        )


def test_society_admin_email_is_normalized_for_creation_and_login(
    client: TestClient,
    tenant_data: dict[str, object],
) -> None:
    super_admin = tenant_data["super_admin"]
    suffix = uuid4().hex
    mixed_case_email = f"Admin-{suffix}@Example.com"
    initial_password = f"Case-Check-{suffix}!"
    create_payload = {
        "first_name": "Case",
        "last_name": "Admin",
        "email": mixed_case_email,
        "initial_password": initial_password,
    }

    created = client.post(
        "/api/v1/auth/society-admins",
        headers=bearer_headers(super_admin),
        json=create_payload,
    )
    assert created.status_code == 201
    normalized_email = mixed_case_email.lower()
    assert created.json()["email"] == normalized_email
    assert created.json()["person"]["email"] == normalized_email

    duplicate = client.post(
        "/api/v1/auth/society-admins",
        headers=bearer_headers(super_admin),
        json={**create_payload, "email": normalized_email},
    )
    assert duplicate.status_code == 409

    login = client.post(
        "/api/v1/auth/login",
        json={"email": mixed_case_email, "password": initial_password},
    )
    assert login.status_code == 200
