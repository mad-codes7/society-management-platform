from __future__ import annotations
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.property import Building, Floor, Unit, UnitType


class PropertyRepository:

    # Building methods
    def create_building(self, db: Session, building: Building) -> Building:
        db.add(building)
        db.flush()
        db.refresh(building)
        return building

    def get_building_by_id(self, db: Session, building_id: UUID) -> Optional[Building]:
        return db.get(Building, building_id)

    def list_buildings_by_society(self, db: Session, society_id: UUID) -> List[Building]:
        stmt = select(Building).where(Building.society_id == society_id).order_by(Building.name)
        return list(db.scalars(stmt).all())

    # Floor methods
    def create_floor(self, db: Session, floor: Floor) -> Floor:
        db.add(floor)
        db.flush()
        db.refresh(floor)
        return floor

    def get_floor_by_id(self, db: Session, floor_id: UUID) -> Optional[Floor]:
        return db.get(Floor, floor_id)

    def list_floors_by_building(self, db: Session, building_id: UUID) -> List[Floor]:
        stmt = select(Floor).where(Floor.building_id == building_id).order_by(Floor.floor_number)
        return list(db.scalars(stmt).all())

    # UnitType methods
    def create_unit_type(self, db: Session, unit_type: UnitType) -> UnitType:
        db.add(unit_type)
        db.flush()
        db.refresh(unit_type)
        return unit_type

    def get_unit_type_by_id(self, db: Session, unit_type_id: UUID) -> Optional[UnitType]:
        return db.get(UnitType, unit_type_id)

    def list_unit_types_by_society(self, db: Session, society_id: UUID) -> List[UnitType]:
        stmt = select(UnitType).where(UnitType.society_id == society_id)
        return list(db.scalars(stmt).all())

    # Unit methods
    def create_unit(self, db: Session, unit: Unit) -> Unit:
        db.add(unit)
        db.flush()
        db.refresh(unit)
        return unit

    def get_unit_by_id(self, db: Session, unit_id: UUID) -> Optional[Unit]:
        return db.get(Unit, unit_id)

    def list_units_by_society(self, db: Session, society_id: UUID, building_id: Optional[UUID] = None) -> List[Unit]:
        query = select(Unit).where(Unit.society_id == society_id)
        if building_id:
            query = query.where(Unit.building_id == building_id)
        return list(db.scalars(query.order_by(Unit.unit_number)).all())
