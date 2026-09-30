from __future__ import annotations
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.modules.society.schemas import (
    SocietyCreate,
    SocietyListResponse,
    SocietyResponse,
    SocietyUpdate,
)
from app.modules.society.service import SocietyService


router = APIRouter(
    prefix="/api/v1/societies",
    tags=["Societies"],
    dependencies=[Depends(require_super_admin)],
)

service = SocietyService()


@router.post(
    "",
    response_model=SocietyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_society(
    data: SocietyCreate,
    db: Session = Depends(get_db),
):
    return service.create(db, data)


@router.get(
    "",
    response_model=SocietyListResponse,
)
def list_societies(
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    societies, total = service.list(
        db=db,
        search=search,
        limit=limit,
        offset=offset,
    )

    return SocietyListResponse(
        items=societies,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{society_id}",
    response_model=SocietyResponse,
)
def get_society(
    society_id: UUID,
    db: Session = Depends(get_db),
):
    return service.get(db, society_id)


@router.patch(
    "/{society_id}",
    response_model=SocietyResponse,
)
def update_society(
    society_id: UUID,
    data: SocietyUpdate,
    db: Session = Depends(get_db),
):
    return service.update(db, society_id, data)


@router.patch(
    "/{society_id}/activate",
    response_model=SocietyResponse,
)
def activate_society(
    society_id: UUID,
    db: Session = Depends(get_db),
):
    return service.change_status(
        db,
        society_id,
        "ACTIVE",
    )


@router.patch(
    "/{society_id}/suspend",
    response_model=SocietyResponse,
)
def suspend_society(
    society_id: UUID,
    db: Session = Depends(get_db),
):
    return service.change_status(
        db,
        society_id,
        "SUSPENDED",
    )