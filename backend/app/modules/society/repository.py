from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.society import Society


class SocietyRepository:

    def create(
        self,
        db: Session,
        society: Society,
    ) -> Society:
        db.add(society)
        db.flush()
        db.refresh(society)
        return society

    def get_by_id(
        self,
        db: Session,
        society_id: UUID,
    ) -> Society | None:
        return db.get(Society, society_id)

    def get_by_name(
        self,
        db: Session,
        name: str,
    ) -> Society | None:
        stmt = select(Society).where(Society.name == name)
        return db.scalar(stmt)

    def list(
        self,
        db: Session,
        search: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Society], int]:

        query = select(Society)

        if search:
            search_pattern = f"%{search}%"

            query = query.where(
                or_(
                    Society.name.ilike(search_pattern),
                    Society.registration_no.ilike(search_pattern),
                )
            )

        count_query = select(func.count()).select_from(
            query.subquery()
        )

        total = db.scalar(count_query) or 0

        query = (
            query
            .order_by(Society.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        societies = list(db.scalars(query).all())

        return societies, total

    def update(
        self,
        db: Session,
        society: Society,
        values: dict,
    ) -> Society:

        for field, value in values.items():
            setattr(society, field, value)

        db.flush()
        db.refresh(society)

        return society