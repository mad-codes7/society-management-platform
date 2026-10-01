from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.modules.audit.service import audit_service
from app.modules.rbac.repository import RbacRepository
from app.modules.rbac.schemas import PermissionCreate, PermissionUpdate, RoleCreate, RoleUpdate


class RbacService:
    def __init__(self, repository: Optional[RbacRepository] = None) -> None:
        self.repository = repository or RbacRepository()

    @staticmethod
    def _commit(db: Session, detail: str = "RBAC operation conflicted with existing data.") -> None:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from None

    def list_roles(self, db: Session) -> list[Role]:
        return self.repository.list_roles(db)

    def list_permissions(self, db: Session) -> list[Permission]:
        return self.repository.list_permissions(db)

    def create_role(self, db: Session, data: RoleCreate, actor_user_id: UUID) -> Role:
        role = Role(name=data.name, description=data.description, is_active=True)
        try:
            self.repository.create_role(db, role)
            audit_service.record(db, action="role_created", entity_type="role", entity_id=role.role_id,
                                 actor_user_id=actor_user_id, after_data={"name": role.name})
            self._commit(db, "A role with this name already exists.")
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="A role with this name already exists.") from None
        db.refresh(role)
        return role

    def update_role(self, db: Session, role_id: UUID, data: RoleUpdate, actor_user_id: UUID) -> Role:
        role = self.repository.get_role(db, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="Role not found.")
        before = {"name": role.name, "description": role.description, "is_active": role.is_active}
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(role, field, value)
        audit_service.record(db, action="role_updated", entity_type="role", entity_id=role.role_id,
                             actor_user_id=actor_user_id, before_data=before,
                             after_data={"name": role.name, "description": role.description, "is_active": role.is_active})
        self.repository.update_role(db, role)
        self._commit(db, "A role with this name already exists.")
        db.refresh(role)
        return role

    def delete_role(self, db: Session, role_id: UUID, actor_user_id: UUID) -> None:
        role = self.repository.get_role(db, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="Role not found.")
        audit_service.record(db, action="role_deleted", entity_type="role", entity_id=role.role_id,
                             actor_user_id=actor_user_id, before_data={"name": role.name})
        self.repository.delete_role(db, role)
        self._commit(db)

    def create_permission(self, db: Session, data: PermissionCreate, actor_user_id: UUID) -> Permission:
        permission = Permission(**data.model_dump())
        try:
            self.repository.create_permission(db, permission)
            audit_service.record(db, action="permission_created", entity_type="permission", entity_id=permission.permission_id,
                                 actor_user_id=actor_user_id, after_data={"code": permission.code})
            self._commit(db, "A permission with this code already exists.")
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail="A permission with this code already exists.") from None
        db.refresh(permission)
        return permission

    def update_permission(self, db: Session, permission_id: UUID, data: PermissionUpdate, actor_user_id: UUID) -> Permission:
        permission = self.repository.get_permission(db, permission_id)
        if permission is None:
            raise HTTPException(status_code=404, detail="Permission not found.")
        before = {"description": permission.description, "module": permission.module}
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(permission, field, value)
        self.repository.update_permission(db, permission)
        audit_service.record(db, action="permission_updated", entity_type="permission", entity_id=permission.permission_id,
                             actor_user_id=actor_user_id, before_data=before,
                             after_data={"description": permission.description, "module": permission.module})
        self._commit(db)
        db.refresh(permission)
        return permission

    def delete_permission(self, db: Session, permission_id: UUID, actor_user_id: UUID) -> None:
        permission = self.repository.get_permission(db, permission_id)
        if permission is None:
            raise HTTPException(status_code=404, detail="Permission not found.")
        audit_service.record(db, action="permission_deleted", entity_type="permission", entity_id=permission.permission_id,
                             actor_user_id=actor_user_id, before_data={"code": permission.code})
        self.repository.delete_permission(db, permission)
        self._commit(db)

    def assign_permission(self, db: Session, role_id: UUID, permission_id: UUID, actor_user_id: UUID) -> None:
        role = self.repository.get_role(db, role_id)
        permission = self.repository.get_permission(db, permission_id)
        if role is None or permission is None:
            raise HTTPException(status_code=404, detail="Role or permission not found.")
        if self.repository.get_role_permission(db, role_id, permission_id):
            raise HTTPException(status_code=409, detail="Permission is already assigned to this role.")
        self.repository.create_role_permission(
            db, RolePermission(role_id=role_id, permission_id=permission_id)
        )
        audit_service.record(db, action="role_permission_assigned", entity_type="role_permission",
                             actor_user_id=actor_user_id, after_data={"role_id": str(role_id), "permission_id": str(permission_id)})
        self._commit(db, "Permission is already assigned to this role.")

    def remove_permission(self, db: Session, role_id: UUID, permission_id: UUID, actor_user_id: UUID) -> None:
        assignment = self.repository.get_role_permission(db, role_id, permission_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail="Role permission assignment not found.")
        self.repository.delete_role_permission(db, assignment)
        audit_service.record(db, action="role_permission_removed", entity_type="role_permission",
                             actor_user_id=actor_user_id, before_data={"role_id": str(role_id), "permission_id": str(permission_id)})
        self._commit(db)

    def assign_role(self, db: Session, membership_id: UUID, role_id: UUID, actor_user_id: UUID) -> None:
        membership = self.repository.get_membership(db, membership_id)
        role = self.repository.get_role(db, role_id)
        if membership is None or role is None:
            raise HTTPException(status_code=404, detail="Membership or role not found.")
        if (
            membership.status != "ACTIVE"
            or membership.society.status != "ACTIVE"
            or not role.is_active
        ):
            raise HTTPException(status_code=409, detail="Membership and role must be active.")
        if self.repository.get_user_role(db, membership_id, role_id):
            raise HTTPException(status_code=409, detail="Role is already assigned to this membership.")
        self.repository.create_user_role(
            db, UserRole(membership_id=membership_id, role_id=role_id)
        )
        audit_service.record(db, action="membership_role_assigned", entity_type="user_role",
                             actor_user_id=actor_user_id, society_id=membership.society_id,
                             after_data={"membership_id": str(membership_id), "role_id": str(role_id)})
        self._commit(db, "Role is already assigned to this membership.")

    def remove_role(self, db: Session, membership_id: UUID, role_id: UUID, actor_user_id: UUID) -> None:
        assignment = self.repository.get_user_role(db, membership_id, role_id)
        membership = self.repository.get_membership(db, membership_id)
        if assignment is None or membership is None:
            raise HTTPException(status_code=404, detail="Membership role assignment not found.")
        self.repository.delete_user_role(db, assignment)
        audit_service.record(db, action="membership_role_removed", entity_type="user_role",
                             actor_user_id=actor_user_id, society_id=membership.society_id,
                             before_data={"membership_id": str(membership_id), "role_id": str(role_id)})
        self._commit(db)