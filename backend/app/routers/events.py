from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.farms import CurrentFarm
from app.schemas.event import EventSearchParams, EventSearchResult, FarmEventCreate, FarmEventRead
from app.services.events import (
    EventDateInPastError,
    create_event,
    list_events_of_farm,
    search_events,
)
from app.services.farms import get_farm_owned_by

router = APIRouter(prefix="/events", tags=["farm events"])


# Browsing farm experiences needs no account, like the product search.
@router.get("/search", response_model=list[EventSearchResult])
def search(
    params: Annotated[EventSearchParams, Query()], db: DatabaseSession
) -> list[EventSearchResult]:
    return search_events(db, params)


@router.get("/mine", response_model=list[FarmEventRead])
def list_my_events(farmer: CurrentFarmer, db: DatabaseSession) -> list[FarmEventRead]:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        return []
    return list_events_of_farm(db, farm)


@router.post("", response_model=FarmEventRead, status_code=status.HTTP_201_CREATED)
def create_my_event(
    details: FarmEventCreate, farm: CurrentFarm, db: DatabaseSession
) -> FarmEventRead:
    try:
        event = create_event(db, farm, details)
    except EventDateInPastError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Event date cannot be in the past",
        ) from None
    return FarmEventRead.from_event(event, reserved_spots=0)
