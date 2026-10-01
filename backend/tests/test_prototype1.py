from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import SocietyMembership, User
from test_auth_tenancy import PASSWORD, bearer_headers, create_society_admin, tenant_data


def test_prototype1_admin_rbac_audit_flow(client, db_session: Session, tenant_data) -> None:
    super_admin = tenant_data["super_admin"]
    login = client.post(
        "/api/v1/auth/login",
        json={"email": super_admin.email, "password": PASSWORD},
    )
    assert login.status_code == 200

    society_response = client.post(
        "/api/v1/societies",
        headers=bearer_headers(super_admin),
        json={"name": f"Prototype 1 Society {uuid4().hex}"},
    )
    assert society_response.status_code == 201
    society_id = society_response.json()["society_id"]

    admin_password = "Prototype-Admin-Password-1!"
    admin_response = client.post(
        "/api/v1/auth/society-admins",
        headers=bearer_headers(super_admin),
        json={
            "first_name": "Prototype",
            "last_name": "Admin",
            "email": f"prototype-admin-{uuid4().hex}@example.com",
            "initial_password": admin_password,
        },
    )
    assert admin_response.status_code == 201
    admin_id = admin_response.json()["user_id"]

    membership_response = client.post(
        f"/api/v1/auth/users/{admin_id}/memberships",
        headers=bearer_headers(super_admin),
        json={"society_id": society_id},
    )
    assert membership_response.status_code == 201
    membership_id = membership_response.json()["membership_id"]

    role_response = client.post(
        "/api/v1/rbac/roles",
        headers=bearer_headers(super_admin),
        json={"name": f"Prototype Reader {uuid4().hex}"},
    )
    permission_response = client.post(
        "/api/v1/rbac/permissions",
        headers=bearer_headers(super_admin),
        json={"code": "society:read", "module": "society"},
    )
    assert role_response.status_code == 201
    assert permission_response.status_code == 201
    role_id = role_response.json()["role_id"]
    permission_id = permission_response.json()["permission_id"]

    assert client.post(
        f"/api/v1/rbac/roles/{role_id}/permissions/{permission_id}",
        headers=bearer_headers(super_admin),
    ).status_code == 204
    assert client.post(
        f"/api/v1/rbac/memberships/{membership_id}/roles/{role_id}",
        headers=bearer_headers(super_admin),
    ).status_code == 204

    admin_login = client.post(
        "/api/v1/auth/login",
        json={"email": admin_response.json()["email"], "password": admin_password},
    )
    assert admin_login.status_code == 200
    authorized = client.get(
        f"/api/v1/properties/societies/{society_id}/buildings",
        headers={"Authorization": f"Bearer {admin_login.json()['access_token']}"},
    )
    assert authorized.status_code == 200
    unauthorized = client.get(
        f"/api/v1/properties/societies/{society_id}/buildings",
        headers=bearer_headers(tenant_data["regular_user"]),
    )
    assert unauthorized.status_code == 403

    update = client.patch(
        f"/api/v1/societies/{society_id}",
        headers=bearer_headers(super_admin),
        json={"address": "Persisted address"},
    )
    assert update.status_code == 200
    db_session.expire_all()
    assert db_session.get(type(tenant_data["society_a"]), society_id).address == "Persisted address"

    suspend = client.patch(
        f"/api/v1/societies/{society_id}/suspend",
        headers=bearer_headers(super_admin),
    )
    assert suspend.status_code == 200
    db_session.expire_all()
    assert db_session.get(type(tenant_data["society_a"]), society_id).status == "SUSPENDED"

    admin_update = client.patch(
        f"/api/v1/auth/users/{admin_id}",
        headers=bearer_headers(super_admin),
        json={"is_active": False},
    )
    assert admin_update.status_code == 200

    audit_actions = {
        item.action
        for item in db_session.query(AuditLog).all()
        if item.actor_user_id == super_admin.user_id
    }
    assert {
        "login_succeeded",
        "society_created",
        "society_admin_created",
        "society_admin_assigned",
        "role_created",
        "permission_created",
        "role_permission_assigned",
        "membership_role_assigned",
        "society_updated",
        "society_status_changed",
        "society_admin_updated",
    } <= audit_actions

    audit_read = client.get(
        f"/api/v1/audit-logs?society_id={society_id}&action=society_updated",
        headers=bearer_headers(super_admin),
    )
    assert audit_read.status_code == 200
    assert audit_read.json()["total"] >= 1


def test_member_without_effective_permission_receives_403(
    client, tenant_data
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]
    response = client.get(
        f"/api/v1/properties/societies/{society.society_id}/buildings",
        headers=bearer_headers(user),
    )
    assert response.status_code == 403


def test_membership_deactivation_prevents_login_context(
    client, db_session: Session, tenant_data
) -> None:
    user = tenant_data["regular_user"]
    membership = db_session.query(SocietyMembership).filter_by(user_id=user.user_id).one()
    response = client.patch(
        f"/api/v1/auth/memberships/{membership.membership_id}",
        headers=bearer_headers(tenant_data["super_admin"]),
        json={"status": "INACTIVE"},
    )
    assert response.status_code == 200
    denied = client.get(
        f"/api/v1/properties/societies/{membership.society_id}/buildings",
        headers=bearer_headers(user),
    )
    assert denied.status_code == 403


def test_audit_read_is_authorized_paginated_and_tenant_scoped(
    client, db_session: Session, tenant_data
) -> None:
    user = tenant_data["regular_user"]
    society_a = tenant_data["society_a"]
    society_b = tenant_data["society_b"]
    permission = Permission(code="audit:read", module="audit")
    role = Role(name=f"Audit Reader {uuid4().hex}", is_active=True)
    db_session.add_all([permission, role])
    db_session.flush()
    db_session.add_all([
        RolePermission(role_id=role.role_id, permission_id=permission.permission_id),
        UserRole(
            membership_id=db_session.query(SocietyMembership).filter_by(
                user_id=user.user_id, society_id=society_a.society_id
            ).one().membership_id,
            role_id=role.role_id,
        ),
    ])
    db_session.add_all([
        AuditLog(
            actor_user_id=user.user_id,
            society_id=society_a.society_id,
            action="society_updated",
            entity_type="society",
            entity_id=str(society_a.society_id),
            after_data={"address": "A"},
        ),
        AuditLog(
            actor_user_id=user.user_id,
            society_id=society_b.society_id,
            action="society_updated",
            entity_type="society",
            entity_id=str(society_b.society_id),
            after_data={"address": "B"},
        ),
    ])
    db_session.flush()

    response = client.get(
        f"/api/v1/audit-logs?society_id={society_a.society_id}&limit=1&offset=0&action=society_updated",
        headers=bearer_headers(user),
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["society_id"] == str(society_a.society_id)

    cross_society = client.get(
        f"/api/v1/audit-logs?society_id={society_b.society_id}",
        headers=bearer_headers(user),
    )
    assert cross_society.status_code == 403
    assert client.get("/api/v1/audit-logs").status_code == 401


def test_admin_audit_snapshot_contains_all_changed_fields(
    client, db_session: Session, tenant_data
) -> None:
    response, _ = create_society_admin(client, tenant_data["super_admin"])
    user_id = response.json()["user_id"]
    assignment = client.post(
        f"/api/v1/auth/users/{user_id}/memberships",
        headers=bearer_headers(tenant_data["super_admin"]),
        json={"society_id": str(tenant_data["society_a"].society_id)},
    )
    assert assignment.status_code == 201
    updated = client.patch(
        f"/api/v1/auth/users/{user_id}",
        headers=bearer_headers(tenant_data["super_admin"]),
        json={
            "email": f"updated-{uuid4().hex}@example.com",
            "first_name": "Updated",
            "last_name": "Admin",
            "phone": "5551234567",
            "gender": "OTHER",
            "dob": "1990-01-02",
            "is_active": False,
        },
    )
    assert updated.status_code == 200
    audit = db_session.query(AuditLog).filter_by(
        action="society_admin_updated", entity_id=user_id
    ).one()
    assert audit.before_data["is_active"] is True
    assert audit.after_data["email"] == updated.json()["email"]
    assert audit.after_data["first_name"] == "Updated"
    assert audit.after_data["last_name"] == "Admin"
    assert audit.after_data["phone"] == "5551234567"
    assert audit.after_data["gender"] == "OTHER"
    assert audit.after_data["date_of_birth"] == "1990-01-02"
    assert audit.after_data["is_active"] is False
    assert "password" not in str(audit.after_data).lower()
    assert client.get(
        "/api/v1/auth/me", headers=bearer_headers(db_session.get(User, user_id))
    ).status_code == 401


def test_suspended_society_blocks_membership_reactivation_and_access(
    client, db_session: Session, tenant_data
) -> None:
    super_admin = tenant_data["super_admin"]
    admin_response, _ = create_society_admin(client, super_admin)
    membership = client.post(
        f"/api/v1/auth/users/{admin_response.json()['user_id']}/memberships",
        headers=bearer_headers(super_admin),
        json={"society_id": str(tenant_data["society_a"].society_id)},
    ).json()
    client.patch(
        f"/api/v1/societies/{tenant_data['society_a'].society_id}/suspend",
        headers=bearer_headers(super_admin),
    )
    inactive = client.patch(
        f"/api/v1/auth/memberships/{membership['membership_id']}",
        headers=bearer_headers(super_admin),
        json={"status": "INACTIVE"},
    )
    assert inactive.status_code == 200
    reactivation = client.patch(
        f"/api/v1/auth/memberships/{membership['membership_id']}",
        headers=bearer_headers(super_admin),
        json={"status": "ACTIVE"},
    )
    assert reactivation.status_code == 409

    regular_user = tenant_data["regular_user"]
    access = client.get(
        f"/api/v1/properties/societies/{tenant_data['society_a'].society_id}/buildings",
        headers=bearer_headers(regular_user),
    )
    assert access.status_code == 403


def test_duplicate_rbac_assignment_returns_409_and_session_recovers(
    client, tenant_data
) -> None:
    headers = bearer_headers(tenant_data["super_admin"])
    role = client.post(
        "/api/v1/rbac/roles",
        headers=headers,
        json={"name": f"Conflict Role {uuid4().hex}"},
    ).json()
    permission = client.post(
        "/api/v1/rbac/permissions",
        headers=headers,
        json={"code": f"conflict:{uuid4().hex}"},
    ).json()
    assignment_path = f"/api/v1/rbac/roles/{role['role_id']}/permissions/{permission['permission_id']}"
    assert client.post(assignment_path, headers=headers).status_code == 204
    assert client.post(assignment_path, headers=headers).status_code == 409
    recovered = client.post(
        "/api/v1/rbac/roles",
        headers=headers,
        json={"name": f"Recovered Role {uuid4().hex}"},
    )
    assert recovered.status_code == 201