from __future__ import annotations
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.property import Building, Floor, Unit, UnitType
from app.modules.property.repository import PropertyRepository
from app.modules.property.schemas import (
    BuildingCreate,
    BuildingUpdate,
    FloorCreate,
    UnitCreate,
    UnitTypeCreate,
    UnitUpdate,
)
from app.modules.society.repository import SocietyRepository


class PropertyService:

    def __init__(self):
        self.repository = PropertyRepository()
        self.society_repository = SocietyRepository()

    # Building methods
    def create_building(self, db: Session, data: BuildingCreate) -> Building:
        society = self.society_repository.get_by_id(db, data.society_id)
        if not society:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified society does not exist.",
            )

        building = Building(
            society_id=data.society_id,
            name=data.name,
            code=data.code,
            building_type=data.building_type,
            total_floors=data.total_floors,
        )
        building = self.repository.create_building(db, building)

        for floor_num in range(1, data.total_floors + 1):
            floor = Floor(
                building_id=building.building_id,
                floor_number=floor_num,
                floor_name=f"Floor {floor_num}",
            )
            self.repository.create_floor(db, floor)

        db.commit()
        db.refresh(building)
        return building

    def list_buildings(self, db: Session, society_id: UUID) -> List[Building]:
        return self.repository.list_buildings_by_society(db, society_id)

    def get_building_by_id(self, db: Session, building_id: UUID) -> Optional[Building]:
        return self.repository.get_building_by_id(db, building_id)

    # Floor methods
    def list_floors(self, db: Session, building_id: UUID) -> List[Floor]:
        return self.repository.list_floors_by_building(db, building_id)

    # UnitType methods
    def create_unit_type(self, db: Session, data: UnitTypeCreate) -> UnitType:
        society = self.society_repository.get_by_id(db, data.society_id)
        if not society:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specified society does not exist.",
            )

        unit_type = UnitType(
            society_id=data.society_id,
            name=data.name,
            super_builtup_area=data.super_builtup_area,
            carpet_area=data.carpet_area,
        )
        unit_type = self.repository.create_unit_type(db, unit_type)
        db.commit()
        db.refresh(unit_type)
        return unit_type

    def list_unit_types(self, db: Session, society_id: UUID) -> List[UnitType]:
        return self.repository.list_unit_types_by_society(db, society_id)

    # Unit methods
    def create_unit(self, db: Session, data: UnitCreate) -> Unit:
        building = self.repository.get_building_by_id(db, data.building_id)
        if not building or building.society_id != data.society_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Building does not exist or does not belong to the specified society.",
            )

        floor = self.repository.get_floor_by_id(db, data.floor_id)
        if not floor or floor.building_id != data.building_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Floor does not exist or does not belong to the specified building.",
            )

        if data.unit_type_id:
            unit_type = self.repository.get_unit_type_by_id(db, data.unit_type_id)
            if not unit_type or unit_type.society_id != data.society_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unit type does not exist or does not belong to the specified society.",
                )

        unit = Unit(
            society_id=data.society_id,
            building_id=data.building_id,
            floor_id=data.floor_id,
            unit_type_id=data.unit_type_id,
            unit_number=data.unit_number,
            occupancy_status=data.occupancy_status,
            is_commercial=data.is_commercial,
        )
        unit = self.repository.create_unit(db, unit)
        db.commit()
        db.refresh(unit)
        return unit

    def list_units(self, db: Session, society_id: UUID, building_id: Optional[UUID] = None) -> List[Unit]:
        return self.repository.list_units_by_society(db, society_id, building_id)

    def get_unit_by_id(self, db: Session, unit_id: UUID) -> Optional[Unit]:
        return self.repository.get_unit_by_id(db, unit_id)

    def update_unit(self, db: Session, unit_id: UUID, data: UnitUpdate) -> Unit:
        unit = self.repository.get_unit_by_id(db, unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unit not found.",
            )

        if data.unit_type_id:
            unit_type = self.repository.get_unit_type_by_id(db, data.unit_type_id)
            if not unit_type or unit_type.society_id != unit.society_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Unit type does not exist or does not belong to the unit's society.",
                )

        values = data.model_dump(exclude_unset=True)
        for field, value in values.items():
            setattr(unit, field, value)

        db.commit()
        db.refresh(unit)
        return unit
