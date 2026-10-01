# RBAC Foundation

## Purpose

This document defines the authorization conventions for the Society Management Platform Phase 0 foundation.

The RBAC foundation provides reusable server-side authorization for protected APIs.

## Authorization Model

The authorization flow is:

User -> Society Membership -> Role -> Permission

### User

A User represents an authenticated account.

### Society Membership

A SocietyMembership connects a user to a specific society.

Roles are assigned to the society membership rather than directly to the user. This allows the same user to have different roles in different societies.

### Role

A role represents a collection of permissions.

Initial platform roles are defined in the RBAC seed:

- Platform Super Admin
- Society Admin
- Chairman/Secretary
- Treasurer/Accountant
- Facility Manager
- Security Supervisor
- Security Guard
- Owner/Resident
- Tenant
- Family Member
- Vendor
- Auditor/Read-only

### Permission

A permission represents one authorized action and is identified by a unique permission code.

Example: society:read

## Permission Assignment

The relationships are:

Role -> RolePermission -> Permission

SocietyMembership -> UserRole -> Role

A role can have multiple permissions.

A society membership can have multiple distinct roles.

Duplicate role-permission and membership-role assignments are prevented by database constraints.

## API Authorization Pattern

Protected endpoints should enforce permissions on the server.

Use the reusable dependency:

Depends(require_permission("permission:code"))

Example:

@router.get(
    "/societies/{society_id}/buildings",
    dependencies=[Depends(require_permission("society:read"))],
)

The permission dependency:

1. Resolves the authenticated user's tenant context.
2. Identifies the user's society membership.
3. Checks the roles assigned to that membership.
4. Checks whether one of those roles has the requested permission.
5. Rejects the request with HTTP 403 when the permission is missing.

## Tenant-Aware Authorization

Authorization must use the authenticated tenant context.

The API must not trust an arbitrary society_id supplied by the client.

The existing tenant-context dependency resolves the requested society through the authenticated user's active membership.

Therefore, permissions from another society must not grant access.

Cross-tenant access attempts must be rejected.

## Super Admin

A Platform Super Admin has platform-level access.

The existing tenant-context implementation represents this using a platform-level context without a society membership.

The permission dependency therefore allows the Super Admin to proceed without requiring a society-specific role assignment.

## Error Convention

Authentication failures use HTTP 401.

Authorization failures use HTTP 403.

For insufficient permissions, the current authorization dependency returns:

{ "detail": "Insufficient permissions." }

## Security Rules

1. Authorization is enforced server-side.
2. Hiding a UI menu is not considered authorization.
3. Protected APIs must declare their authorization requirement.
4. Tenant scope must be enforced where applicable.
5. Client-supplied society_id must not bypass tenant context.
6. Cross-society access must be rejected.
7. Permission-denied behavior must have automated tests.
8. Database schema changes must use Alembic migrations.

## Phase 0 Scope

Phase 0 provides the reusable RBAC foundation:

- Role model
- Permission model
- Role-permission mapping
- Membership-role mapping
- Permission dependency
- Tenant-aware authorization
- Permission error handling
- Authorization tests

Full role/permission management APIs and the complete business permission catalogue belong to later Prototype 1 work and should be implemented as separate increments.
