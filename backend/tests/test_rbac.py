from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

TESTS_ROOT = Path(__file__).resolve().parent
BACKEND_ROOT = TESTS_ROOT.parent

sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(TESTS_ROOT))

from app.core.dependencies import TenantContext, resolve_tenant_context
from app.core.rbac import require_permission
from app.core.security import create_access_token
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import SocietyMembership, User

from test_auth_tenancy import tenant_data


def bearer_headers(user: User) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token(str(user.user_id))}"
    }


def assign_role(
    db: Session,
    user: User,
    society_id: UUID,
    role: Role,
) -> None:
    membership = (
        db.query(SocietyMembership)
        .filter(
            SocietyMembership.user_id == user.user_id,
            SocietyMembership.society_id == society_id,
        )
        .one()
    )

    db.add(
        UserRole(
            membership_id=membership.membership_id,
            role_id=role.role_id,
        )
    )


def create_rbac_permission(
    db: Session,
    code: str,
) -> Permission:
    permission = Permission(
        code=code,
        description=f"Test permission: {code}",
        module="test",
    )

    db.add(permission)
    db.flush()

    return permission


def create_rbac_role(
    db: Session,
    name: str,
) -> Role:
    role = Role(
        name=name,
        description=f"Test role: {name}",
        is_active=True,
    )

    db.add(role)
    db.flush()

    return role


def grant_permission(
    db: Session,
    role: Role,
    permission: Permission,
) -> None:
    db.add(
        RolePermission(
            role_id=role.role_id,
            permission_id=permission.permission_id,
        )
    )


def test_permission_is_granted_to_user(
    db_session: Session,
    tenant_data,
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]

    permission = create_rbac_permission(
        db_session,
        "test:read",
    )

    role = create_rbac_role(
        db_session,
        "Test Reader",
    )

    grant_permission(
        db_session,
        role,
        permission,
    )

    assign_role(
        db_session,
        user,
        society.society_id,
        role,
    )

    db_session.flush()

    tenant_context = resolve_tenant_context(
        db_session,
        user,
        society.society_id,
    )

    dependency = require_permission("test:read")

    result = dependency(
        society_id=society.society_id,
        tenant_context=tenant_context,
        db=db_session,
    )

    assert result == tenant_context


def test_user_without_permission_is_denied(
    db_session: Session,
    tenant_data,
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]

    tenant_context = resolve_tenant_context(
        db_session,
        user,
        society.society_id,
    )

    dependency = require_permission("test:missing")

    try:
        dependency(
            society_id=society.society_id,
            tenant_context=tenant_context,
            db=db_session,
        )
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Insufficient permissions."


def test_inactive_membership_is_denied(
    db_session: Session,
    tenant_data,
) -> None:
    user = tenant_data["inactive_membership_user"]
    society = tenant_data["society_b"]

    # The user has an INACTIVE membership in Society B.
    # Tenant resolution should therefore reject access before
    # the permission check is reached.

    try:
        resolve_tenant_context(
            db_session,
            user,
            society.society_id,
        )
        assert False, "Expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Not authorized to access this society."


def test_super_admin_bypasses_permission_check(
    db_session: Session,
    tenant_data,
) -> None:
    user = tenant_data["super_admin"]
    society = tenant_data["society_a"]

    tenant_context = resolve_tenant_context(
        db_session,
        user,
        society.society_id,
    )

    assert tenant_context.membership_id is None

    dependency = require_permission("test:anything")

    result = dependency(
        society_id=society.society_id,
        tenant_context=tenant_context,
        db=db_session,
    )

    assert result == tenant_context


def test_permission_from_another_society_is_not_used(
    db_session: Session,
    tenant_data,
) -> None:
    user = tenant_data["regular_user"]
    society_a = tenant_data["society_a"]
    society_b = tenant_data["society_b"]

    permission = create_rbac_permission(
        db_session,
        "test:tenant-specific",
    )

    role = create_rbac_role(
        db_session,
        "Society A Reader",
    )

    grant_permission(
        db_session,
        role,
        permission,
    )

    # The user receives this role only in Society A.
    assign_role(
        db_session,
        user,
        society_a.society_id,
        role,
    )

    db_session.flush()

    dependency = require_permission("test:tenant-specific")

    # Society A: permission should be accepted.
    society_a_context = resolve_tenant_context(
        db_session,
        user,
        society_a.society_id,
    )

    result = dependency(
        society_id=society_a.society_id,
        tenant_context=society_a_context,
        db=db_session,
    )

    assert result == society_a_context

    # Society B: the user has no active membership,
    # so tenant resolution must deny access.
    try:
        resolve_tenant_context(
            db_session,
            user,
            society_b.society_id,
        )
        assert False, "Expected tenant access to be denied"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "Not authorized to access this society."


def test_building_list_requires_society_read_permission(
    client,
    db_session: Session,
    tenant_data,
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]

    permission = create_rbac_permission(
        db_session,
        "society:read",
    )

    role = create_rbac_role(
        db_session,
        "Building Reader",
    )

    grant_permission(
        db_session,
        role,
        permission,
    )

    assign_role(
        db_session,
        user,
        society.society_id,
        role,
    )

    db_session.flush()

    response = client.get(
        f"/api/v1/properties/societies/{society.society_id}/buildings",
        headers=bearer_headers(user),
    )

    assert response.status_code == 200


def test_building_list_denies_user_without_society_read_permission(
    client,
    tenant_data,
) -> None:
    user = tenant_data["regular_user"]
    society = tenant_data["society_a"]

    response = client.get(
        f"/api/v1/properties/societies/{society.society_id}/buildings",
        headers=bearer_headers(user),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Insufficient permissions."
