from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import SocietyMembership


class RbacRepository:
    def create_role(self, db: Session, role: Role) -> Role:
        db.add(role)
        db.flush()
        return role

    def update_role(self, db: Session, role: Role) -> Role:
        db.flush()
        return role

    def delete_role(self, db: Session, role: Role) -> None:
        db.delete(role)

    def create_permission(self, db: Session, permission: Permission) -> Permission:
        db.add(permission)
        db.flush()
        return permission

    def update_permission(self, db: Session, permission: Permission) -> Permission:
        db.flush()
        return permission

    def delete_permission(self, db: Session, permission: Permission) -> None:
        db.delete(permission)

    def create_role_permission(self, db: Session, assignment: RolePermission) -> RolePermission:
        db.add(assignment)
        db.flush()
        return assignment

    def delete_role_permission(self, db: Session, assignment: RolePermission) -> None:
        db.delete(assignment)

    def create_user_role(self, db: Session, assignment: UserRole) -> UserRole:
        db.add(assignment)
        db.flush()
        return assignment

    def delete_user_role(self, db: Session, assignment: UserRole) -> None:
        db.delete(assignment)

    def list_roles(self, db: Session) -> list[Role]:
        return list(db.scalars(select(Role).order_by(Role.name)).all())

    def list_permissions(self, db: Session) -> list[Permission]:
        return list(db.scalars(select(Permission).order_by(Permission.code)).all())

    def get_role(self, db: Session, role_id: UUID) -> Optional[Role]:
        return db.get(Role, role_id)

    def get_permission(self, db: Session, permission_id: UUID) -> Optional[Permission]:
        return db.get(Permission, permission_id)

    def get_membership(self, db: Session, membership_id: UUID) -> Optional[SocietyMembership]:
        return db.get(SocietyMembership, membership_id)

    def get_role_permission(self, db: Session, role_id: UUID, permission_id: UUID) -> Optional[RolePermission]:
        return db.scalar(select(RolePermission).where(
            RolePermission.role_id == role_id,
            RolePermission.permission_id == permission_id,
        ))

    def get_user_role(self, db: Session, membership_id: UUID, role_id: UUID) -> Optional[UserRole]:
        return db.scalar(select(UserRole).where(
            UserRole.membership_id == membership_id,
            UserRole.role_id == role_id,
        ))