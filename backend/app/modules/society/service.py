from __future__ import annotations
from typing import Optional, Tuple, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.society import Society
from app.modules.society.repository import SocietyRepository
from app.modules.society.schemas import SocietyCreate, SocietyUpdate


class SocietyService:

    def __init__(self):
        self.repository = SocietyRepository()

    def create(
        self,
        db: Session,
        data: SocietyCreate,
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

        return self.repository.update(
            db=db,
            society=society,
            values=values,
        )

    def change_status(
        self,
        db: Session,
        society_id: UUID,
        new_status: str,
    ) -> Society:

        society = self.get(db, society_id)

        society.status = new_status

        db.flush()
        db.refresh(society)

        return society