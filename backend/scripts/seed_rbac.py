from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.rbac import Permission, Role, RolePermission


ROLES = [
    {
        "name": "Platform Super Admin",
        "description": "Platform-level administrator with access across societies.",
    },
    {
        "name": "Society Admin",
        "description": "Administrator responsible for managing a society.",
    },
    {
        "name": "Chairman/Secretary",
        "description": "Society leadership role for administrative and governance activities.",
    },
    {
        "name": "Treasurer/Accountant",
        "description": "Responsible for society financial and accounting activities.",
    },
    {
        "name": "Facility Manager",
        "description": "Responsible for society facilities and maintenance activities.",
    },
    {
        "name": "Security Supervisor",
        "description": "Supervises security operations within a society.",
    },
    {
        "name": "Security Guard",
        "description": "Performs security and access-control activities.",
    },
    {
        "name": "Owner/Resident",
        "description": "Society resident who owns a property.",
    },
    {
        "name": "Tenant",
        "description": "Resident occupying a property as a tenant.",
    },
    {
        "name": "Family Member",
        "description": "Family member associated with a society resident.",
    },
    {
        "name": "Vendor",
        "description": "External vendor providing services to the society.",
    },
    {
        "name": "Auditor/Read-only",
        "description": "Read-only access for auditing and review purposes.",
    },
]


# These are foundation-level permissions only.
# Module-specific permissions can be added as the corresponding
# business modules are implemented.
PERMISSIONS = [
    {
        "code": "society:read",
        "description": "View society information.",
        "module": "society",
    },
    {
        "code": "society:manage",
        "description": "Create and update society master data.",
        "module": "society",
    },
    {
        "code": "property:read",
        "description": "View buildings, floors, and units.",
        "module": "property",
    },
    {
        "code": "property:manage",
        "description": "Manage property master data.",
        "module": "property",
    },
    {
        "code": "resident:read",
        "description": "View resident master data.",
        "module": "residents",
    },
    {
        "code": "resident:manage",
        "description": "Manage resident master data.",
        "module": "residents",
    },
    {
        "code": "audit:read",
        "description": "View audit records for the permitted society.",
        "module": "audit",
    },
]


# Initial role-permission mapping.
# This is intentionally minimal because the SRS does not define
# a complete role-permission matrix.
ROLE_PERMISSIONS = {
    "Platform Super Admin": [
        "society:read", "society:manage", "property:read", "property:manage",
        "resident:read", "resident:manage",
        "audit:read",
    ],
    "Society Admin": [
        "society:read", "society:manage", "property:read", "property:manage",
        "resident:read", "resident:manage",
        "audit:read",
    ],
    "Chairman/Secretary": ["society:read", "property:read", "resident:read", "audit:read"],
    "Treasurer/Accountant": ["society:read"],
    "Facility Manager": ["society:read", "property:read", "property:manage"],
    "Security Supervisor": ["society:read", "property:read"],
    "Security Guard": ["society:read"],
    "Owner/Resident": ["society:read", "property:read", "resident:read"],
    "Tenant": ["society:read", "property:read", "resident:read"],
    "Family Member": ["society:read", "resident:read"],
    "Vendor": ["society:read"],
    "Auditor/Read-only": ["society:read", "property:read", "resident:read", "audit:read"],
}


def seed_roles(db) -> dict[str, Role]:
    roles: dict[str, Role] = {}

    for role_data in ROLES:
        role = db.scalar(
            select(Role).where(Role.name == role_data["name"])
        )

        if role is None:
            role = Role(**role_data)
            db.add(role)
            db.flush()
            print(f"Created role: {role.name}")
        else:
            print(f"Role already exists: {role.name}")

        roles[role.name] = role

    return roles


def seed_permissions(db) -> dict[str, Permission]:
    permissions: dict[str, Permission] = {}

    for permission_data in PERMISSIONS:
        permission = db.scalar(
            select(Permission).where(
                Permission.code == permission_data["code"]
            )
        )

        if permission is None:
            permission = Permission(**permission_data)
            db.add(permission)
            db.flush()
            print(f"Created permission: {permission.code}")
        else:
            print(f"Permission already exists: {permission.code}")

        permissions[permission.code] = permission

    return permissions


def seed_role_permissions(
    db,
    roles: dict[str, Role],
    permissions: dict[str, Permission],
) -> None:
    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = roles[role_name]

        for permission_code in permission_codes:
            permission = permissions[permission_code]

            existing = db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == role.role_id,
                    RolePermission.permission_id == permission.permission_id,
                )
            )

            if existing is None:
                db.add(
                    RolePermission(
                        role_id=role.role_id,
                        permission_id=permission.permission_id,
                    )
                )
                print(
                    f"Mapped permission '{permission.code}' "
                    f"to role '{role.name}'"
                )
            else:
                print(
                    f"Mapping already exists: "
                    f"{role.name} -> {permission.code}"
                )


def main() -> int:
    db = SessionLocal()

    try:
        roles = seed_roles(db)
        permissions = seed_permissions(db)
        seed_role_permissions(db, roles, permissions)

        db.commit()

        print("\nRBAC seed completed successfully.")
        print(f"Roles: {len(roles)}")
        print(f"Permissions: {len(permissions)}")

        return 0

    except IntegrityError:
        db.rollback()
        print(
            "Error: database rejected the RBAC seed data.",
            file=sys.stderr,
        )
        return 1

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())