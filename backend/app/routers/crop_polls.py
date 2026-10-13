from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.farms import CurrentFarm
from app.dependencies.path_params import ResourceId
from app.schemas.crop_poll import (
    CropPollCreate,
    CropPollRead,
    CropPollSearchParams,
    CropPollSearchResult,
)
from app.services.crop_polls import (
    CropPollClosedError,
    close_crop_poll,
    create_crop_poll,
    get_crop_poll,
    list_crop_polls_of_farm,
    search_crop_polls,
)
from app.services.farms import get_farm_owned_by

router = APIRouter(prefix="/crop-polls", tags=["crop polls"])


# Browsing what nearby farms are asking about needs no account, like the other searches.
@router.get("/search", response_model=list[CropPollSearchResult])
def search(
    params: Annotated[CropPollSearchParams, Query()], db: DatabaseSession
) -> list[CropPollSearchResult]:
    return search_crop_polls(db, params)


@router.get("/mine", response_model=list[CropPollRead])
def list_my_crop_polls(farmer: CurrentFarmer, db: DatabaseSession) -> list[CropPollRead]:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        return []
    return list_crop_polls_of_farm(db, farm)


@router.post("", response_model=CropPollRead, status_code=status.HTTP_201_CREATED)
def create_my_crop_poll(
    details: CropPollCreate, farm: CurrentFarm, db: DatabaseSession
) -> CropPollRead:
    return create_crop_poll(db, farm, details)


@router.post("/{poll_id}/close", response_model=CropPollRead)
def close_my_crop_poll(
    poll_id: ResourceId, farmer: CurrentFarmer, db: DatabaseSession
) -> CropPollRead:
    poll = get_crop_poll(db, poll_id)
    if poll is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Crop poll not found")
    farm = get_farm_owned_by(db, farmer)
    if farm is None or poll.farm_id != farm.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own crop polls",
        )
    try:
        return close_crop_poll(db, poll)
    except CropPollClosedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This crop poll is already closed"
        ) from None
