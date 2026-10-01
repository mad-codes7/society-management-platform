from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, hash_password, normalize_email, verify_password
from app.models.person import Person
from app.models.user import SocietyMembership, User
from app.modules.audit.service import audit_service
from app.modules.auth.repository import AuthRepository
from app.modules.society.repository import SocietyRepository
from app.modules.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    MembershipSummary,
    SocietyAdminCreateRequest,
    SocietyAdminCreateResponse,
    SocietyAdminResponse,
    SocietyAdminUpdateRequest,
    SocietyAdminPersonResponse,
    SocietyMembershipCreateRequest,
    SocietyMembershipCreateResponse,
    SocietyMembershipUpdateRequest,
    TokenResponse,
)


class AuthService:
    def __init__(
        self,
        repository: Optional[AuthRepository] = None,
        society_repository: Optional[SocietyRepository] = None,
    ) -> None:
        self.repository = repository or AuthRepository()
        self.society_repository = society_repository or SocietyRepository()

    def create_society_membership(
        self,
        db: Session,
        user_id: UUID,
        data: SocietyMembershipCreateRequest,
        actor_user_id: Optional[UUID] = None,
    ) -> SocietyMembershipCreateResponse:
        user = self.repository.get_user_by_id(db, user_id)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active user not found.",
            )

        society = self.society_repository.get_by_id(db, data.society_id)
        if society is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Society not found.",
            )
        if society.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Society is not active.",
            )

        existing = self.repository.get_membership_for_user_in_society(
            db,
            user_id,
            data.society_id,
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A membership already exists for this user and society.",
            )

        membership = SocietyMembership(
            user_id=user_id,
            society_id=data.society_id,
            status="ACTIVE",
        )
        try:
            self.repository.create_membership(db, membership)
            audit_service.record(
                db,
                action="society_admin_assigned",
                entity_type="society_membership",
                entity_id=membership.membership_id,
                actor_user_id=actor_user_id,
                society_id=data.society_id,
                after_data={"user_id": str(user_id), "status": membership.status},
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A membership already exists for this user and society.",
            ) from None
        except Exception:
            db.rollback()
            raise

        return SocietyMembershipCreateResponse.model_validate(membership)

    def create_society_admin(
        self,
        db: Session,
        data: SocietyAdminCreateRequest,
        actor_user_id: Optional[UUID] = None,
    ) -> SocietyAdminCreateResponse:
        email = normalize_email(str(data.email))
        if (
            self.repository.get_user_by_email(db, email)
            or self.repository.get_person_by_email(db, email)
            or (data.phone and self.repository.get_person_by_phone(db, data.phone))
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists with one or more provided contact details.",
            )

        person = Person(
            first_name=data.first_name,
            last_name=data.last_name,
            email=email,
            phone=data.phone,
            gender=data.gender,
            dob=data.dob,
        )
        user = User(
            email=email,
            password_hash=hash_password(data.initial_password.get_secret_value()),
            person=person,
            is_active=True,
            is_super_admin=False,
        )

        try:
            self.repository.create_person(db, person)
            self.repository.create_user(db, user)
            audit_service.record(
                db,
                action="society_admin_created",
                entity_type="user",
                entity_id=user.user_id,
                actor_user_id=actor_user_id,
                after_data={"email": user.email, "is_active": user.is_active},
            )
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists with one or more provided contact details.",
            ) from None
        except Exception:
            db.rollback()
            raise

        return SocietyAdminCreateResponse(
            user_id=user.user_id,
            email=user.email,
            is_active=user.is_active,
            is_super_admin=user.is_super_admin,
            person=SocietyAdminPersonResponse.model_validate(person),
        )

    def update_society_admin(
        self,
        db: Session,
        user_id: UUID,
        data: SocietyAdminUpdateRequest,
        actor_user_id: Optional[UUID] = None,
    ) -> SocietyAdminResponse:
        user = self.repository.get_user_by_id(db, user_id)
        if user is None or user.is_super_admin or user.person is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Society admin not found.")

        before = {"email": user.email, "is_active": user.is_active}
        values = data.model_dump(exclude_unset=True)
        user.is_active = values.pop("is_active", user.is_active)
        for field, value in values.items():
            setattr(user.person, field, value)

        audit_service.record(
            db,
            action="society_admin_updated",
            entity_type="user",
            entity_id=user.user_id,
            actor_user_id=actor_user_id,
            before_data=before,
            after_data={"email": user.email, "is_active": user.is_active},
        )
        db.commit()
        db.refresh(user)
        return SocietyAdminResponse.model_validate(user)

    def update_membership(
        self,
        db: Session,
        membership_id: UUID,
        data: SocietyMembershipUpdateRequest,
        actor_user_id: Optional[UUID] = None,
    ) -> SocietyMembershipCreateResponse:
        membership = self.repository.get_membership_by_id(db, membership_id)
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found.")
        before = {"status": membership.status}
        membership.status = data.status
        audit_service.record(
            db,
            action="society_admin_membership_updated",
            entity_type="society_membership",
            entity_id=membership.membership_id,
            actor_user_id=actor_user_id,
            society_id=membership.society_id,
            before_data=before,
            after_data={"status": membership.status},
        )
        db.commit()
        db.refresh(membership)
        return SocietyMembershipCreateResponse.model_validate(membership)

    def login(self, db: Session, data: LoginRequest) -> TokenResponse:
        user = self.repository.get_user_by_email(db, normalize_email(str(data.email)))
        if user is None or not verify_password(
            data.password.get_secret_value(),
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive.",
            )

        expires_in = settings.jwt_access_token_expire_minutes * 60
        access_token = create_access_token(str(user.user_id))

        self.repository.update_last_login_at(db, user)
        audit_service.record(
            db,
            action="login_succeeded",
            entity_type="user",
            entity_id=user.user_id,
            actor_user_id=user.user_id,
        )
        db.commit()

        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=expires_in,
        )

    def get_current_user(self, db: Session, user: User) -> CurrentUserResponse:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        memberships = self.repository.get_active_memberships_for_user(
            db,
            user.user_id,
        )
        return CurrentUserResponse(
            user_id=user.user_id,
            email=user.email,
            person_id=user.person_id,
            is_super_admin=user.is_super_admin,
            is_active=user.is_active,
            memberships=[MembershipSummary.model_validate(item) for item in memberships],
        )
