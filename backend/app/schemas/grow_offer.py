from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models.grow_offer import CropCommitment, GrowOffer, GrowOfferStatus
from app.models.product import ProductUnit
from app.schemas.common import (
    CropName,
    DatabaseId,
    NearbySearchParams,
    PositivePrice,
    blank_to_none,
)
from app.schemas.product import MAX_QUANTITY

MAX_MINIMUM_CUSTOMERS = 10_000


class GrowOfferCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    crop_name: CropName
    expected_quantity: int = Field(gt=0, le=MAX_QUANTITY)
    unit: ProductUnit
    estimated_price: PositivePrice
    planting_date: date
    expected_harvest_date: date
    minimum_customers: int = Field(gt=0, le=MAX_MINIMUM_CUSTOMERS)

    @model_validator(mode="after")
    def harvest_is_not_before_planting(self) -> Self:
        if self.expected_harvest_date < self.planting_date:
            raise ValueError("expected_harvest_date must not be before planting_date")
        return self


class GrowOfferRead(BaseModel):
    id: int
    farm_id: int
    crop_name: str
    expected_quantity: int
    unit: ProductUnit
    estimated_price: Decimal
    planting_date: date
    expected_harvest_date: date
    minimum_customers: int
    status: GrowOfferStatus
    created_at: datetime
    # Progress toward confirmation, shown as "12 / 20 customers committed".
    committed_customers: int
    committed_quantity: int

    @classmethod
    def from_offer(cls, offer: GrowOffer, committed_customers: int, committed_quantity: int) -> Self:
        return cls(
            id=offer.id,
            farm_id=offer.farm_id,
            crop_name=offer.crop_name,
            expected_quantity=offer.expected_quantity,
            unit=offer.unit,
            estimated_price=offer.estimated_price,
            planting_date=offer.planting_date,
            expected_harvest_date=offer.expected_harvest_date,
            minimum_customers=offer.minimum_customers,
            status=offer.status,
            created_at=offer.created_at,
            committed_customers=committed_customers,
            committed_quantity=committed_quantity,
        )


class GrowOfferSearchParams(NearbySearchParams):
    """Query parameters of the search for grow offers a customer can join."""

    model_config = ConfigDict(str_strip_whitespace=True)

    crop: Annotated[str | None, BeforeValidator(blank_to_none)] = Field(
        default=None, max_length=80, description="Text to look for in crop names."
    )


class GrowOfferFarm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_name: str
    city: str
    state: str


class GrowOfferSearchResult(BaseModel):
    offer: GrowOfferRead
    farm: GrowOfferFarm
    distance_miles: float


class GrowOfferDetail(BaseModel):
    """One offer with the farm that made it, as shown above its crop journey."""

    offer: GrowOfferRead
    farm: GrowOfferFarm


class CropCommitmentCreate(BaseModel):
    grow_offer_id: DatabaseId
    quantity: int = Field(gt=0, le=MAX_QUANTITY)


class CropCommitmentRead(BaseModel):
    id: int
    quantity: int
    created_at: datetime
    offer: GrowOfferRead
    farm: GrowOfferFarm

    @classmethod
    def from_commitment(
        cls, commitment: CropCommitment, committed_customers: int, committed_quantity: int
    ) -> Self:
        offer = commitment.grow_offer
        return cls(
            id=commitment.id,
            quantity=commitment.quantity,
            created_at=commitment.created_at,
            offer=GrowOfferRead.from_offer(offer, committed_customers, committed_quantity),
            farm=GrowOfferFarm.model_validate(offer.farm),
        )
