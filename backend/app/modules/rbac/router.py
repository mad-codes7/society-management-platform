from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.models.user import User
from app.modules.rbac.schemas import PermissionCreate, PermissionResponse, PermissionUpdate, RoleCreate, RoleResponse, RoleUpdate
from app.modules.rbac.service import RbacService


router = APIRouter(prefix="/api/v1/rbac", tags=["RBAC"], dependencies=[Depends(require_super_admin)])
service = RbacService()


@router.get("/roles", response_model=list[RoleResponse])
def list_roles(db: Session = Depends(get_db)):
    return service.list_roles(db)


@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
def create_role(data: RoleCreate, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)):
    return service.create_role(db, data, current_user.user_id)


@router.patch("/roles/{role_id}", response_model=RoleResponse)
def update_role(role_id: UUID, data: RoleUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)):
    return service.update_role(db, role_id, data, current_user.user_id)


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(role_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)) -> None:
    service.delete_role(db, role_id, current_user.user_id)


@router.get("/permissions", response_model=list[PermissionResponse])
def list_permissions(db: Session = Depends(get_db)):
    return service.list_permissions(db)


@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def create_permission(data: PermissionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)):
    return service.create_permission(db, data, current_user.user_id)


@router.patch("/permissions/{permission_id}", response_model=PermissionResponse)
def update_permission(permission_id: UUID, data: PermissionUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)):
    return service.update_permission(db, permission_id, data, current_user.user_id)


@router.delete("/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_permission(permission_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)) -> None:
    service.delete_permission(db, permission_id, current_user.user_id)


@router.post("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_permission(role_id: UUID, permission_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)) -> None:
    service.assign_permission(db, role_id, permission_id, current_user.user_id)


@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_permission(role_id: UUID, permission_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)) -> None:
    service.remove_permission(db, role_id, permission_id, current_user.user_id)


@router.post("/memberships/{membership_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_role(membership_id: UUID, role_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)) -> None:
    service.assign_role(db, membership_id, role_id, current_user.user_id)


@router.delete("/memberships/{membership_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_role(membership_id: UUID, role_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_super_admin)) -> None:
    service.remove_role(db, membership_id, role_id, current_user.user_id)