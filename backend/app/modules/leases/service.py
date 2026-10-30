from __future__ import annotations

import re
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.history import Lease
from app.modules.audit.service import audit_service
from app.modules.leases.repository import LeaseRepository
from app.modules.leases.schemas import LeaseCreate, LeaseUpdate

LEASE_CONFLICT_MESSAGE = (
    "Lease dates overlap an existing lease for this unit."
)


class LeaseService:
    def __init__(self, repository: Optional[LeaseRepository] = None) -> None:
        self.repository = repository or LeaseRepository()

    @staticmethod
    def _parse_date(value: str, field_name: str) -> date:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a valid ISO date (YYYY-MM-DD).",
            )
        try:
            return date.fromisoformat(value)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a valid ISO date (YYYY-MM-DD).",
            ) from None

    @staticmethod
    def _status_for_end_date(lease_end: Optional[date]) -> str:
        return "ACTIVE" if lease_end is None or lease_end >= date.today() else "INACTIVE"

    @staticmethod
    def _audit_data(lease: Lease) -> dict[str, object]:
        return {
            "owner_person_id": (
                str(lease.owner_person_id) if lease.owner_person_id is not None else None
            ),
            "lease_start": lease.lease_start.isoformat(),
            "lease_end": lease.lease_end.isoformat() if lease.lease_end else None,
            "status": lease.status,
        }

    @staticmethod
    def _is_lease_exclusion_violation(error: IntegrityError) -> bool:
        diagnostic = getattr(error.orig, "diag", None)
        return (
            getattr(diagnostic, "constraint_name", None)
            == "ex_leases_active_unit_dates"
        )

    def _validate_person(
        self,
        db: Session,
        society_id: UUID,
        person_id: Optional[UUID],
        field_name: str,
    ) -> None:
        if person_id is not None and not self.repository.person_belongs_to_society(
            db, society_id, person_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{field_name} not found in this society.",
            )

    def _validate_no_overlap(
        self,
        db: Session,
        society_id: UUID,
        unit_id: UUID,
        lease_start: date,
        lease_end: Optional[date],
        exclude_lease_id: Optional[UUID] = None,
    ) -> None:
        if self.repository.has_overlapping_lease(
            db,
            society_id,
            unit_id,
            lease_start,
            lease_end,
            exclude_lease_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=LEASE_CONFLICT_MESSAGE,
            )

    @staticmethod
    def _commit(db: Session, lease: Lease) -> Lease:
        db.commit()
        db.refresh(lease)
        return lease

    def create(
        self,
        db: Session,
        society_id: UUID,
        data: LeaseCreate,
        actor_user_id: UUID,
    ) -> Lease:
        lease_start = self._parse_date(data.lease_start, "lease_start")
        lease_end = (
            self._parse_date(data.lease_end, "lease_end")
            if data.lease_end is not None
            else None
        )
        if lease_end is not None and lease_end < lease_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lease_end cannot be before lease_start.",
            )
        if self.repository.get_unit(db, society_id, data.unit_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unit not found in this society.",
            )
        self._validate_person(
            db, society_id, data.tenant_person_id, "Tenant person"
        )
        self._validate_person(db, society_id, data.owner_person_id, "Owner person")
        self._validate_no_overlap(
            db, society_id, data.unit_id, lease_start, lease_end
        )

        lease = Lease(
            society_id=society_id,
            unit_id=data.unit_id,
            tenant_person_id=data.tenant_person_id,
            owner_person_id=data.owner_person_id,
            lease_start=lease_start,
            lease_end=lease_end,
            status=self._status_for_end_date(lease_end),
        )
        try:
            lease = self.repository.create(db, lease)
            audit_service.record(
                db,
                action="lease_created",
                entity_type="lease",
                entity_id=lease.lease_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                after_data=self._audit_data(lease),
            )
            return self._commit(db, lease)
        except IntegrityError as error:
            db.rollback()
            if self._is_lease_exclusion_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=LEASE_CONFLICT_MESSAGE,
                ) from None
            raise

    def update(
        self,
        db: Session,
        society_id: UUID,
        lease_id: UUID,
        data: LeaseUpdate,
        actor_user_id: UUID,
    ) -> Lease:
        lease = self.repository.get(db, society_id, lease_id)
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lease not found in this society.",
            )
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one lease field must be provided.",
            )
        if "owner_person_id" in changes:
            self._validate_person(
                db, society_id, changes["owner_person_id"], "Owner person"
            )

        lease_end = lease.lease_end
        if "lease_end" in changes:
            lease_end = (
                self._parse_date(changes["lease_end"], "lease_end")
                if changes["lease_end"] is not None
                else None
            )
            if lease_end is not None and lease_end < lease.lease_start:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="lease_end cannot be before lease_start.",
                )
            self._validate_no_overlap(
                db,
                society_id,
                lease.unit_id,
                lease.lease_start,
                lease_end,
                lease.lease_id,
            )

        before = self._audit_data(lease)
        if "owner_person_id" in changes:
            lease.owner_person_id = changes["owner_person_id"]
        if "lease_end" in changes:
            lease.lease_end = lease_end
            lease.status = self._status_for_end_date(lease_end)
        after = self._audit_data(lease)
        action = "lease_terminated" if "lease_end" in changes else "lease_updated"
        try:
            audit_service.record(
                db,
                action=action,
                entity_type="lease",
                entity_id=lease.lease_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=before,
                after_data=after,
            )
            return self._commit(db, lease)
        except IntegrityError as error:
            db.rollback()
            if self._is_lease_exclusion_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=LEASE_CONFLICT_MESSAGE,
                ) from None
            raise

    def end(
        self,
        db: Session,
        society_id: UUID,
        lease_id: UUID,
        lease_end_value: str,
        actor_user_id: UUID,
    ) -> Lease:
        lease = self.repository.get(db, society_id, lease_id)
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lease not found in this society.",
            )
        if lease.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only active leases can be ended.",
            )
        lease_end = self._parse_date(lease_end_value, "lease_end")
        if lease_end < lease.lease_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lease_end cannot be before lease_start.",
            )
        self._validate_no_overlap(
            db,
            society_id,
            lease.unit_id,
            lease.lease_start,
            lease_end,
            lease.lease_id,
        )
        before = self._audit_data(lease)
        lease.lease_end = lease_end
        lease.status = self._status_for_end_date(lease_end)
        try:
            audit_service.record(
                db,
                action="lease_terminated",
                entity_type="lease",
                entity_id=lease.lease_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=before,
                after_data=self._audit_data(lease),
            )
            return self._commit(db, lease)
        except IntegrityError as error:
            db.rollback()
            if self._is_lease_exclusion_violation(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=LEASE_CONFLICT_MESSAGE,
                ) from None
            raise

    def get(
        self,
        db: Session,
        society_id: UUID,
        lease_id: UUID,
    ) -> Lease:
        lease = self.repository.get(db, society_id, lease_id)
        if lease is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lease not found in this society.",
            )
        return lease

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        tenant_person_id: Optional[UUID],
    ) -> list[Lease]:
        return self.repository.list(db, society_id, unit_id, tenant_person_id)


lease_service = LeaseService()
