from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.user import SocietyMembership, User
from test_auth_tenancy import PASSWORD, bearer_headers, tenant_data


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

    admin_response = client.post(
        "/api/v1/auth/society-admins",
        headers=bearer_headers(super_admin),
        json={
            "first_name": "Prototype",
            "last_name": "Admin",
            "email": f"prototype-admin-{uuid4().hex}@example.com",
            "initial_password": "Prototype-Admin-Password-1!",
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
    authorized = client.get(
        f"/api/v1/properties/societies/{society_id}/buildings",
        headers=bearer_headers(db_session.get(User, admin_id)),
    )
    assert authorized.status_code == 200

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