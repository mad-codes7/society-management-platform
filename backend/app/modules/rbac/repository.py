from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import SocietyMembership


class RbacRepository:
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