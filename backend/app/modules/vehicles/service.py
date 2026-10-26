from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.history import Vehicle
from app.modules.audit.service import audit_service
from app.modules.vehicles.repository import VehicleRepository
from app.modules.vehicles.schemas import VehicleCreate, VehicleUpdate

DUPLICATE_REGISTRATION_MESSAGE = (
    "A vehicle with this registration number is already registered in this society."
)


class VehicleService:
    def __init__(self, repository: Optional[VehicleRepository] = None) -> None:
        self.repository = repository or VehicleRepository()

    @staticmethod
    def _is_duplicate_registration(error: IntegrityError) -> bool:
        diagnostic = getattr(error.orig, "diag", None)
        return (
            getattr(diagnostic, "constraint_name", None)
            == "uq_vehicles_society_registration"
        )

    @staticmethod
    def _audit_data(vehicle: Vehicle) -> dict[str, object]:
        return {
            "registration_number": vehicle.registration_number,
            "vehicle_type": vehicle.vehicle_type,
            "person_id": str(vehicle.person_id) if vehicle.person_id else None,
            "unit_id": str(vehicle.unit_id) if vehicle.unit_id else None,
            "status": vehicle.status,
        }

    def _validate_association(
        self,
        db: Session,
        society_id: UUID,
        person_id: Optional[UUID],
        unit_id: Optional[UUID],
    ) -> None:
        if unit_id is not None and self.repository.get_unit(
            db, society_id, unit_id
        ) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unit not found in this society.",
            )
        if person_id is not None and not self.repository.person_belongs_to_society(
            db, society_id, person_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Person not found in this society.",
            )
        if (
            person_id is not None
            and unit_id is not None
            and not self.repository.has_active_resident_association(
                db, society_id, unit_id, person_id
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Person must be an active resident of the specified unit.",
            )

    @staticmethod
    def _commit(db: Session, vehicle: Vehicle) -> Vehicle:
        db.commit()
        db.refresh(vehicle)
        return vehicle

    def register(
        self,
        db: Session,
        society_id: UUID,
        data: VehicleCreate,
        actor_user_id: UUID,
    ) -> Vehicle:
        self._validate_association(
            db, society_id, data.person_id, data.unit_id
        )
        vehicle = Vehicle(
            society_id=society_id,
            person_id=data.person_id,
            unit_id=data.unit_id,
            registration_number=data.registration_number,
            vehicle_type=data.vehicle_type,
            make_model=data.make_model,
            colour=data.colour,
            status="ACTIVE",
        )
        try:
            self.repository.create(db, vehicle)
            audit_service.record(
                db,
                action="vehicle_registered",
                entity_type="vehicle",
                entity_id=vehicle.vehicle_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                after_data=self._audit_data(vehicle),
            )
            return self._commit(db, vehicle)
        except IntegrityError as error:
            db.rollback()
            if self._is_duplicate_registration(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=DUPLICATE_REGISTRATION_MESSAGE,
                ) from None
            raise

    def update(
        self,
        db: Session,
        society_id: UUID,
        vehicle_id: UUID,
        data: VehicleUpdate,
        actor_user_id: UUID,
    ) -> Vehicle:
        vehicle = self.get(db, society_id, vehicle_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one vehicle field must be provided.",
            )
        for field in ("registration_number", "vehicle_type"):
            if field in changes and changes[field] is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} cannot be null.",
                )

        person_id = changes.get("person_id", vehicle.person_id)
        unit_id = changes.get("unit_id", vehicle.unit_id)
        self._validate_association(db, society_id, person_id, unit_id)
        before = self._audit_data(vehicle)
        for field, value in changes.items():
            setattr(vehicle, field, value)
        try:
            audit_service.record(
                db,
                action="vehicle_updated",
                entity_type="vehicle",
                entity_id=vehicle.vehicle_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=before,
                after_data=self._audit_data(vehicle),
            )
            return self._commit(db, vehicle)
        except IntegrityError as error:
            db.rollback()
            if self._is_duplicate_registration(error):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=DUPLICATE_REGISTRATION_MESSAGE,
                ) from None
            raise

    def deactivate(
        self,
        db: Session,
        society_id: UUID,
        vehicle_id: UUID,
        actor_user_id: UUID,
    ) -> Vehicle:
        vehicle = self.get(db, society_id, vehicle_id)
        if vehicle.status == "INACTIVE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vehicle is already inactive.",
            )
        before = self._audit_data(vehicle)
        vehicle.status = "INACTIVE"
        try:
            audit_service.record(
                db,
                action="vehicle_deactivated",
                entity_type="vehicle",
                entity_id=vehicle.vehicle_id,
                actor_user_id=actor_user_id,
                society_id=society_id,
                before_data=before,
                after_data=self._audit_data(vehicle),
            )
            return self._commit(db, vehicle)
        except IntegrityError:
            db.rollback()
            raise

    def get(
        self,
        db: Session,
        society_id: UUID,
        vehicle_id: UUID,
    ) -> Vehicle:
        vehicle = self.repository.get(db, society_id, vehicle_id)
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Vehicle not found in this society.",
            )
        return vehicle

    def list(
        self,
        db: Session,
        society_id: UUID,
        unit_id: Optional[UUID],
        person_id: Optional[UUID],
        vehicle_status: Optional[str],
    ) -> list[Vehicle]:
        return self.repository.list(
            db, society_id, unit_id, person_id, vehicle_status
        )


vehicle_service = VehicleService()
