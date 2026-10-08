from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.path_params import ResourceId
from app.models.farm import Farm
from app.schemas.farm import FarmRead, FarmWrite
from app.services.farms import (
    FarmAlreadyExistsError,
    create_farm,
    get_farm,
    get_farm_owned_by,
    update_farm,
)

router = APIRouter(prefix="/farms", tags=["farms"])


def _farm_not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farm not found")


@router.post("", response_model=FarmRead, status_code=status.HTTP_201_CREATED)
def create_my_farm(farm_details: FarmWrite, farmer: CurrentFarmer, db: DatabaseSession) -> Farm:
    try:
        return create_farm(db, farmer, farm_details)
    except FarmAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a farm",
        ) from None


# Declared before /{farm_id} so that "me" is never read as a farm id.
@router.get("/me", response_model=FarmRead)
def read_my_farm(farmer: CurrentFarmer, db: DatabaseSession) -> Farm:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not created a farm yet",
        )
    return farm


# Farm profiles are public marketplace listings, so reading one needs no account.
@router.get("/{farm_id}", response_model=FarmRead)
def read_farm(farm_id: ResourceId, db: DatabaseSession) -> Farm:
    farm = get_farm(db, farm_id)
    if farm is None:
        raise _farm_not_found()
    return farm


@router.put("/{farm_id}", response_model=FarmRead)
def update_my_farm(
    farm_id: ResourceId, farm_details: FarmWrite, farmer: CurrentFarmer, db: DatabaseSession
) -> Farm:
    farm = get_farm(db, farm_id)
    if farm is None:
        raise _farm_not_found()
    if farm.owner_id != farmer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own farm",
        )
    return update_farm(db, farm, farm_details)
