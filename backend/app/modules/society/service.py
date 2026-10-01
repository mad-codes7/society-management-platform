from __future__ import annotations
from typing import Optional, Tuple, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.society import Society
from app.modules.society.repository import SocietyRepository
from app.modules.society.schemas import SocietyCreate, SocietyUpdate
from app.modules.audit.service import audit_service


class SocietyService:

    def __init__(self):
        self.repository = SocietyRepository()

    def create(
        self,
        db: Session,
        data: SocietyCreate,
        actor_user_id: Optional[UUID] = None,
    ) -> Society:

        existing = self.repository.get_by_name(db, data.name)

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Society with this name already exists.",
            )

        society = Society(
            name=data.name,
            registration_no=data.registration_no,
            address=data.address,
            contact_phone=data.contact_phone,
            contact_email=data.contact_email,
            logo_path=data.logo_path,
            status="ACTIVE",
        )

        society = self.repository.create(db, society)

        audit_service.record(
            db,
            action="society_created",
            entity_type="society",
            entity_id=society.society_id,
            actor_user_id=actor_user_id,
            society_id=society.society_id,
            after_data={"name": society.name, "status": society.status},
        )

        db.commit()
        db.refresh(society)

        return society

    def get(
        self,
        db: Session,
        society_id: UUID,
    ) -> Society:

        society = self.repository.get_by_id(db, society_id)

        if not society:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Society not found.",
            )

        return society

    def list(
        self,
        db: Session,
        search: Optional[str],
        limit: int,
        offset: int,
    ):
        return self.repository.list(
            db=db,
            search=search,
            limit=limit,
            offset=offset,
        )

    def update(
        self,
        db: Session,
        society_id: UUID,
        data: SocietyUpdate,
        actor_user_id: Optional[UUID] = None,
    ) -> Society:

        society = self.get(db, society_id)

        values = data.model_dump(exclude_unset=True)

        if "name" in values:
            existing = self.repository.get_by_name(db, values["name"])

            if existing and existing.society_id != society_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Society with this name already exists.",
                )

        before = {field: getattr(society, field) for field in values}
        society = self.repository.update(
            db=db,
            society=society,
            values=values,
        )
        audit_service.record(
            db,
            action="society_updated",
            entity_type="society",
            entity_id=society.society_id,
            actor_user_id=actor_user_id,
            society_id=society.society_id,
            before_data=before,
            after_data=values,
        )
        db.commit()
        db.refresh(society)
        return society

    def change_status(
        self,
        db: Session,
        society_id: UUID,
        new_status: str,
        actor_user_id: Optional[UUID] = None,
    ) -> Society:

        society = self.get(db, society_id)

        before = {"status": society.status}
        society.status = new_status

        db.flush()
        audit_service.record(
            db,
            action="society_status_changed",
            entity_type="society",
            entity_id=society.society_id,
            actor_user_id=actor_user_id,
            society_id=society.society_id,
            before_data=before,
            after_data={"status": society.status},
        )
        db.commit()
        db.refresh(society)

        return society