from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_super_admin
from app.models.user import User
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    SocietyAdminCreateRequest,
    SocietyAdminCreateResponse,
    SocietyMembershipCreateRequest,
    SocietyMembershipCreateResponse,
    TokenResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)

service = AuthService()


@router.post(
    "/society-admins",
    response_model=SocietyAdminCreateResponse,
    status_code=201,
)
def create_society_admin(
    data: SocietyAdminCreateRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_super_admin),
) -> SocietyAdminCreateResponse:
    return service.create_society_admin(db, data)


@router.post(
    "/users/{user_id}/memberships",
    response_model=SocietyMembershipCreateResponse,
    status_code=201,
    dependencies=[Depends(require_super_admin)],
)
def create_user_membership(
    user_id: UUID,
    data: SocietyMembershipCreateRequest,
    db: Session = Depends(get_db),
) -> SocietyMembershipCreateResponse:
    return service.create_society_membership(db, user_id, data)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return service.login(db, data)


@router.get("/me", response_model=CurrentUserResponse)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CurrentUserResponse:
    return service.get_current_user(db, current_user)
