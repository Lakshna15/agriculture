import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.models.product import ProductCategory, ProductUnit
from app.schemas.common import NearbySearchParams, PositivePrice, blank_to_none

# PostgreSQL's integer type tops out just above two billion; this keeps stock
# figures well inside it and inside anything a real farm would list.
MAX_QUANTITY = 1_000_000

ProductQuantity = Annotated[int, Field(ge=0, le=MAX_QUANTITY)]


class ProductDetails(BaseModel):
    """Descriptive fields shared by creating and replacing a product."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    category: ProductCategory
    description: Annotated[str | None, BeforeValidator(blank_to_none)] = Field(
        default=None, max_length=2000
    )
    # Two decimal places at most, so a price is always a whole number of cents.
    price: PositivePrice
    unit: ProductUnit
    harvest_date: date | None = None
    available_from: date | None = None
    available_until: date | None = None
    organic: bool = False
    active: bool = True

    @model_validator(mode="after")
    def availability_window_is_ordered(self) -> Self:
        if (
            self.available_from is not None
            and self.available_until is not None
            and self.available_until < self.available_from
        ):
            raise ValueError("available_until must not be before available_from")
        return self


class ProductCreate(ProductDetails):
    quantity_available: ProductQuantity = 0


class ProductUpdate(ProductDetails):
    """Replaces a product's details.

    Stock is deliberately not part of this schema. Quantity changes go through
    the inventory endpoint so that each one is recorded in the history.
    """


class InventoryUpdate(BaseModel):
    quantity_available: ProductQuantity


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_id: int
    name: str
    category: ProductCategory
    description: str | None
    price: Decimal
    unit: ProductUnit
    quantity_available: int
    harvest_date: date | None
    available_from: date | None
    available_until: date | None
    organic: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class ProductSearchSort(enum.StrEnum):
    DISTANCE = "distance"
    PRICE = "price"
    HARVEST_DATE = "harvest_date"


class ProductSearchParams(NearbySearchParams):
    """Query parameters of the product search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: Annotated[str | None, BeforeValidator(blank_to_none)] = Field(
        default=None, max_length=100, description="Text to look for in product names."
    )
    category: ProductCategory | None = None
    available_only: bool = Field(
        default=True,
        description="Only products that are in stock and inside their availability window today.",
    )
    sort: ProductSearchSort = ProductSearchSort.DISTANCE


class SearchResultProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: ProductCategory
    description: str | None
    unit: ProductUnit
    organic: bool
    available_from: date | None
    available_until: date | None


class SearchResultFarm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_name: str
    city: str
    state: str
    pickup_available: bool
    delivery_available: bool


class ProductSearchResult(BaseModel):
    product: SearchResultProduct
    farm: SearchResultFarm
    distance_miles: float
    price: Decimal
    quantity_available: int
    harvest_date: date | None
