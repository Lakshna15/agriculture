from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from app.models.crop_request import CropRequestStatus, RequestFrequency, Season
from app.models.product import ProductUnit
from app.schemas.common import CropName, blank_to_none
from app.schemas.product import MAX_QUANTITY


class CropRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    crop_name: CropName
    quantity: int = Field(gt=0, le=MAX_QUANTITY)
    unit: ProductUnit
    frequency: RequestFrequency
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    # How far the customer is willing to travel for this crop.
    radius_miles: int = Field(ge=1, le=500)
    preferred_season: Season | None = None
    notes: Annotated[str | None, BeforeValidator(blank_to_none)] = Field(
        default=None, max_length=1000
    )


class CropRequestRead(BaseModel):
    """A crop request as its own customer sees it, location included."""

    id: int
    crop_name: str
    quantity: int
    unit: ProductUnit
    frequency: RequestFrequency
    latitude: float
    longitude: float
    radius_miles: int
    preferred_season: Season | None
    notes: str | None
    status: CropRequestStatus
    created_at: datetime
    # True once the customer has joined an active grow offer for this crop.
    # Such a request no longer counts as unmet demand.
    covered_by_commitment: bool


class CropDemand(BaseModel):
    """Open requests for one crop and unit near a farm, added together.

    This is everything a farmer is shown about demand. It carries no
    location, no customer identity and no free-text notes.
    """

    crop_name: str
    unit: ProductUnit
    customers_interested: int
    # Weekly requests plus monthly requests spread over the weeks of a year.
    estimated_weekly_quantity: float
    # The total of requests that ask for a single delivery.
    one_time_quantity: int
