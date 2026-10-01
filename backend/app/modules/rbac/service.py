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

    def list_roles(self, db: Session) -> list[Role]:
        return self.repository.list_roles(db)

    def list_permissions(self, db: Session) -> list[Permission]:
        return self.repository.list_permissions(db)

    def create_role(self, db: Session, data: RoleCreate, actor_user_id: UUID) -> Role:
        role = Role(name=data.name, description=data.description, is_active=True)
        db.add(role)
        try:
            db.flush()
            audit_service.record(db, action="role_created", entity_type="role", entity_id=role.role_id,
                                 actor_user_id=actor_user_id, after_data={"name": role.name})
            db.commit()
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
        db.commit()
        db.refresh(role)
        return role

    def delete_role(self, db: Session, role_id: UUID, actor_user_id: UUID) -> None:
        role = self.repository.get_role(db, role_id)
        if role is None:
            raise HTTPException(status_code=404, detail="Role not found.")
        audit_service.record(db, action="role_deleted", entity_type="role", entity_id=role.role_id,
                             actor_user_id=actor_user_id, before_data={"name": role.name})
        db.delete(role)
        db.commit()

    def create_permission(self, db: Session, data: PermissionCreate, actor_user_id: UUID) -> Permission:
        permission = Permission(**data.model_dump())
        db.add(permission)
        try:
            db.flush()
            audit_service.record(db, action="permission_created", entity_type="permission", entity_id=permission.permission_id,
                                 actor_user_id=actor_user_id, after_data={"code": permission.code})
            db.commit()
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
        audit_service.record(db, action="permission_updated", entity_type="permission", entity_id=permission.permission_id,
                             actor_user_id=actor_user_id, before_data=before,
                             after_data={"description": permission.description, "module": permission.module})
        db.commit()
        db.refresh(permission)
        return permission

    def delete_permission(self, db: Session, permission_id: UUID, actor_user_id: UUID) -> None:
        permission = self.repository.get_permission(db, permission_id)
        if permission is None:
            raise HTTPException(status_code=404, detail="Permission not found.")
        audit_service.record(db, action="permission_deleted", entity_type="permission", entity_id=permission.permission_id,
                             actor_user_id=actor_user_id, before_data={"code": permission.code})
        db.delete(permission)
        db.commit()

    def assign_permission(self, db: Session, role_id: UUID, permission_id: UUID, actor_user_id: UUID) -> None:
        role = self.repository.get_role(db, role_id)
        permission = self.repository.get_permission(db, permission_id)
        if role is None or permission is None:
            raise HTTPException(status_code=404, detail="Role or permission not found.")
        if self.repository.get_role_permission(db, role_id, permission_id):
            raise HTTPException(status_code=409, detail="Permission is already assigned to this role.")
        db.add(RolePermission(role_id=role_id, permission_id=permission_id))
        audit_service.record(db, action="role_permission_assigned", entity_type="role_permission",
                             actor_user_id=actor_user_id, after_data={"role_id": str(role_id), "permission_id": str(permission_id)})
        db.commit()

    def remove_permission(self, db: Session, role_id: UUID, permission_id: UUID, actor_user_id: UUID) -> None:
        assignment = self.repository.get_role_permission(db, role_id, permission_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail="Role permission assignment not found.")
        db.delete(assignment)
        audit_service.record(db, action="role_permission_removed", entity_type="role_permission",
                             actor_user_id=actor_user_id, before_data={"role_id": str(role_id), "permission_id": str(permission_id)})
        db.commit()

    def assign_role(self, db: Session, membership_id: UUID, role_id: UUID, actor_user_id: UUID) -> None:
        membership = self.repository.get_membership(db, membership_id)
        role = self.repository.get_role(db, role_id)
        if membership is None or role is None:
            raise HTTPException(status_code=404, detail="Membership or role not found.")
        if membership.status != "ACTIVE" or not role.is_active:
            raise HTTPException(status_code=409, detail="Membership and role must be active.")
        if self.repository.get_user_role(db, membership_id, role_id):
            raise HTTPException(status_code=409, detail="Role is already assigned to this membership.")
        db.add(UserRole(membership_id=membership_id, role_id=role_id))
        audit_service.record(db, action="membership_role_assigned", entity_type="user_role",
                             actor_user_id=actor_user_id, society_id=membership.society_id,
                             after_data={"membership_id": str(membership_id), "role_id": str(role_id)})
        db.commit()

    def remove_role(self, db: Session, membership_id: UUID, role_id: UUID, actor_user_id: UUID) -> None:
        assignment = self.repository.get_user_role(db, membership_id, role_id)
        membership = self.repository.get_membership(db, membership_id)
        if assignment is None or membership is None:
            raise HTTPException(status_code=404, detail="Membership role assignment not found.")
        db.delete(assignment)
        audit_service.record(db, action="membership_role_removed", entity_type="user_role",
                             actor_user_id=actor_user_id, society_id=membership.society_id,
                             before_data={"membership_id": str(membership_id), "role_id": str(role_id)})
        db.commit()