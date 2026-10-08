from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
)

# The marketplace currently serves farms in the United States: 50 states plus DC.
US_STATE_CODES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
    "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)


def _blank_to_none(value: object) -> object:
    """Treat an empty or whitespace-only optional text field as not provided."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _require_us_state(state_code: str) -> str:
    if state_code not in US_STATE_CODES:
        raise ValueError("must be a two-letter US state code")
    return state_code


# The pattern accepts either case because it is checked before the value is uppercased.
UsStateCode = Annotated[
    str,
    StringConstraints(to_upper=True, pattern=r"^[A-Za-z]{2}$"),
    AfterValidator(_require_us_state),
]
UsZipCode = Annotated[str, StringConstraints(pattern=r"^\d{5}(-\d{4})?$")]
PhoneNumber = Annotated[str, StringConstraints(pattern=r"^[0-9+().\-\s]{7,30}$")]


class FarmWrite(BaseModel):
    """Fields a farmer may set when creating or replacing a farm profile.

    Ownership and identifiers are deliberately absent, so a request body can
    never assign a farm to another user.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    farm_name: str = Field(min_length=1, max_length=120)
    description: Annotated[str | None, BeforeValidator(_blank_to_none)] = Field(
        default=None, max_length=2000
    )
    address: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)
    state: UsStateCode
    zip_code: UsZipCode
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    phone: Annotated[PhoneNumber | None, BeforeValidator(_blank_to_none)] = None
    pickup_available: bool = True
    delivery_available: bool = False


class FarmRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    farm_name: str
    description: str | None
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    phone: str | None
    pickup_available: bool
    delivery_available: bool
    created_at: datetime
    updated_at: datetime
