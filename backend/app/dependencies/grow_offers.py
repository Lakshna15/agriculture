from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.path_params import ResourceId
from app.models.grow_offer import GrowOffer
from app.services.farms import get_farm_owned_by
from app.services.grow_offers import get_grow_offer


def get_existing_grow_offer(offer_id: ResourceId, db: DatabaseSession) -> GrowOffer:
    """Load a grow offer for reading. No ownership is required."""
    offer = get_grow_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grow offer not found")
    return offer


ExistingGrowOffer = Annotated[GrowOffer, Depends(get_existing_grow_offer)]


def get_owned_grow_offer(offer_id: ResourceId, farmer: CurrentFarmer, db: DatabaseSession) -> GrowOffer:
    """Load a grow offer and confirm it belongs to the signed-in farmer's farm."""
    offer = get_grow_offer(db, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grow offer not found")

    farm = get_farm_owned_by(db, farmer)
    if farm is None or offer.farm_id != farm.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own grow offers",
        )
    return offer


OwnedGrowOffer = Annotated[GrowOffer, Depends(get_owned_grow_offer)]
