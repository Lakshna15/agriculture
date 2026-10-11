from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.models.farm import Farm
from app.services.farms import get_farm_owned_by


def get_current_farm(farmer: CurrentFarmer, db: DatabaseSession) -> Farm:
    """The signed-in farmer's farm, required before they can list anything on it."""
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Create your farm first",
        )
    return farm


CurrentFarm = Annotated[Farm, Depends(get_current_farm)]
