from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
)

from app.models.crop_update import CropStage
from app.schemas.common import blank_to_none

IMAGE_URL_MAX_LENGTH = 500
_http_url = TypeAdapter(HttpUrl)


def _require_https_url(url: str) -> str:
    """Accept only a well-formed https link, and keep it as the text that was sent."""
    parsed = _http_url.validate_python(url)
    if parsed.scheme != "https":
        raise ValueError("image_url must be an https link")
    return url


ImageUrl = Annotated[
    str,
    Field(max_length=IMAGE_URL_MAX_LENGTH),
    AfterValidator(_require_https_url),
]


class CropUpdateCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    stage: CropStage
    message: str = Field(min_length=1, max_length=2000)
    image_url: Annotated[ImageUrl | None, BeforeValidator(blank_to_none)] = None


class CropUpdateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grow_offer_id: int
    stage: CropStage
    message: str
    image_url: str | None
    created_at: datetime
