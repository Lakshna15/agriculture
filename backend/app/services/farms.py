from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.user import User
from app.schemas.farm import FarmWrite


class FarmAlreadyExistsError(Exception):
    """Raised when a farmer who already owns a farm tries to create another."""


def get_farm(db: Session, farm_id: int) -> Farm | None:
    return db.get(Farm, farm_id)


def get_farm_owned_by(db: Session, owner: User) -> Farm | None:
    return db.scalar(select(Farm).where(Farm.owner_id == owner.id))


def create_farm(db: Session, owner: User, farm_details: FarmWrite) -> Farm:
    # FarmWrite carries only farmer-editable fields, so unpacking it cannot
    # set the owner or the id. The owner always comes from the session.
    farm = Farm(owner_id=owner.id, **farm_details.model_dump())
    db.add(farm)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if isinstance(error.orig, UniqueViolation):
            raise FarmAlreadyExistsError(owner.id) from error
        raise
    return farm


def update_farm(db: Session, farm: Farm, farm_details: FarmWrite) -> Farm:
    for field_name, value in farm_details.model_dump().items():
        setattr(farm, field_name, value)
    db.commit()
    db.refresh(farm)
    return farm
