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


class PropertyService:

    def __init__(self):
        self.repository = PropertyRepository()

    # Building methods
    def create_building(self, db: Session, data: BuildingCreate) -> Building:
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

    # Floor methods
    def list_floors(self, db: Session, building_id: UUID) -> List[Floor]:
        return self.repository.list_floors_by_building(db, building_id)

    # UnitType methods
    def create_unit_type(self, db: Session, data: UnitTypeCreate) -> UnitType:
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
        if not building:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Building not found.",
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

    def update_unit(self, db: Session, unit_id: UUID, data: UnitUpdate) -> Unit:
        unit = self.repository.get_unit_by_id(db, unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unit not found.",
            )

        values = data.model_dump(exclude_unset=True)
        for field, value in values.items():
            setattr(unit, field, value)

        db.commit()
        db.refresh(unit)
        return unit
