from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field, StringConstraints

# An id of a database row sent in a request body. The bounds match
# PostgreSQL's integer type, so an out-of-range id is a validation error
# rather than a database error.
DatabaseId = Annotated[int, Field(ge=1, le=2_147_483_647)]


def to_whole_cents(amount: Decimal) -> Decimal:
    """Give an amount exactly two decimal places, so "4.5" is stored and returned as "4.50"."""
    return amount.quantize(Decimal("0.01"))


# A price in dollars. decimal_places=2 has already rejected fractions of a
# cent by the time the amount is padded to two places.
PositivePrice = Annotated[
    Decimal, Field(gt=0, max_digits=10, decimal_places=2), AfterValidator(to_whole_cents)
]
PriceOrFree = Annotated[
    Decimal, Field(ge=0, max_digits=10, decimal_places=2), AfterValidator(to_whole_cents)
]


def normalize_crop_name(name: str) -> str:
    """Give a crop name one canonical spelling: single spaces, each word capitalized.

    "sweet  CORN" and "Sweet corn" both become "Sweet Corn", so crop requests
    and grow offers for the same crop can be matched and counted together.
    Singular and plural forms are still different names.
    """
    return " ".join(word.capitalize() for word in name.split())


CropName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=2, max_length=80),
    AfterValidator(normalize_crop_name),
]


def blank_to_none(value: object) -> object:
    """Treat an empty or whitespace-only optional text field as not provided."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


class NearbySearchParams(BaseModel):
    """Query parameters shared by every search for things near a point."""

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    radius_miles: float = Field(default=25, gt=0, le=500, allow_inf_nan=False)
    limit: int = Field(default=50, ge=1, le=100)
