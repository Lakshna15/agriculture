from fastapi import APIRouter

from app.database import DatabaseSession
from app.dependencies.farms import CurrentFarm
from app.schemas.crop_request import CropDemand
from app.services.crop_requests import summarize_demand_near_farm

router = APIRouter(prefix="/demand", tags=["local demand"])


# The farm is always the signed-in farmer's own. There is no way to ask about
# demand around an arbitrary point, which would make it easier to work out
# where individual requests come from.
@router.get("", response_model=list[CropDemand])
def read_demand_near_my_farm(farm: CurrentFarm, db: DatabaseSession) -> list[CropDemand]:
    return summarize_demand_near_farm(db, farm)
