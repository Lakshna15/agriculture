from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.farms import CurrentFarm
from app.dependencies.grow_offers import ExistingGrowOffer, OwnedGrowOffer
from app.models.crop_update import CropUpdate
from app.schemas.crop_update import CropUpdateCreate, CropUpdateRead
from app.schemas.grow_offer import (
    GrowOfferCreate,
    GrowOfferDetail,
    GrowOfferRead,
    GrowOfferSearchParams,
    GrowOfferSearchResult,
)
from app.services.crop_journey import (
    GrowOfferClosedError,
    OfferNotConfirmedError,
    StageRegressionError,
    list_crop_updates,
    post_crop_update,
)
from app.services.farms import get_farm_owned_by
from app.services.grow_offers import (
    GrowOfferNotCancellableError,
    GrowOfferNotReadyError,
    HarvestDateInPastError,
    cancel_grow_offer,
    complete_grow_offer,
    create_grow_offer,
    list_grow_offers_of_farm,
    read_grow_offer_with_farm,
    search_grow_offers,
)

router = APIRouter(prefix="/grow-offers", tags=["grow offers"])


# Browsing what farmers are offering to grow needs no account, like the other searches.
@router.get("/search", response_model=list[GrowOfferSearchResult])
def search(
    params: Annotated[GrowOfferSearchParams, Query()], db: DatabaseSession
) -> list[GrowOfferSearchResult]:
    return search_grow_offers(db, params)


@router.get("/mine", response_model=list[GrowOfferRead])
def list_my_grow_offers(farmer: CurrentFarmer, db: DatabaseSession) -> list[GrowOfferRead]:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        return []
    return list_grow_offers_of_farm(db, farm)


@router.post("", response_model=GrowOfferRead, status_code=status.HTTP_201_CREATED)
def create_my_grow_offer(
    details: GrowOfferCreate, farm: CurrentFarm, db: DatabaseSession
) -> GrowOfferRead:
    try:
        return create_grow_offer(db, farm, details)
    except HarvestDateInPastError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Expected harvest date cannot be in the past",
        ) from None


# An offer and its crop journey are public, like the offer search they are reached from.
@router.get("/{offer_id}", response_model=GrowOfferDetail)
def read_grow_offer_detail(offer: ExistingGrowOffer, db: DatabaseSession) -> GrowOfferDetail:
    return read_grow_offer_with_farm(db, offer)


@router.post("/{offer_id}/cancel", response_model=GrowOfferRead)
def cancel_my_grow_offer(offer: OwnedGrowOffer, db: DatabaseSession) -> GrowOfferRead:
    try:
        return cancel_grow_offer(db, offer)
    except GrowOfferNotCancellableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an open or confirmed grow offer can be cancelled",
        ) from None


@router.post("/{offer_id}/complete", response_model=GrowOfferRead)
def complete_my_grow_offer(offer: OwnedGrowOffer, db: DatabaseSession) -> GrowOfferRead:
    try:
        return complete_grow_offer(db, offer)
    except GrowOfferNotReadyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only a grow offer whose crop is ready can be marked completed",
        ) from None


@router.get("/{offer_id}/updates", response_model=list[CropUpdateRead])
def list_grow_offer_updates(offer: ExistingGrowOffer, db: DatabaseSession) -> list[CropUpdate]:
    return list_crop_updates(db, offer)


@router.post(
    "/{offer_id}/updates", response_model=CropUpdateRead, status_code=status.HTTP_201_CREATED
)
def post_grow_offer_update(
    details: CropUpdateCreate, offer: OwnedGrowOffer, db: DatabaseSession
) -> CropUpdate:
    try:
        return post_crop_update(db, offer, details)
    except GrowOfferClosedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This grow offer is closed and takes no more updates",
        ) from None
    except OfferNotConfirmedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Until the offer is confirmed, only a PLANNED update can be posted",
        ) from None
    except StageRegressionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The crop is already at {error.latest_stage.value}; updates cannot go back a stage",
        ) from None
