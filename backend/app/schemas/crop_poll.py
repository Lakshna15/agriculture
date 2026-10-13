from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.crop_poll import CropPoll, CropPollStatus
from app.schemas.common import CropName, DatabaseId, NearbySearchParams

DEFAULT_POLL_QUESTION = "What should I grow next?"
MIN_POLL_OPTIONS = 2
MAX_POLL_OPTIONS = 8


class CropPollCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(default=DEFAULT_POLL_QUESTION, min_length=1, max_length=200)
    # Crop names in the same canonical spelling as crop requests and grow offers.
    options: list[CropName] = Field(min_length=MIN_POLL_OPTIONS, max_length=MAX_POLL_OPTIONS)

    @model_validator(mode="after")
    def options_are_distinct(self) -> Self:
        if len(set(self.options)) != len(self.options):
            raise ValueError("options must not repeat a crop")
        return self


class CropPollOptionRead(BaseModel):
    id: int
    crop_name: str
    votes: int


class CropPollRead(BaseModel):
    """A poll with its vote counts. Who voted for what is never included."""

    id: int
    farm_id: int
    question: str
    status: CropPollStatus
    created_at: datetime
    options: list[CropPollOptionRead]
    total_votes: int

    @classmethod
    def from_poll(cls, poll: CropPoll, votes_by_option: dict[int, int]) -> Self:
        options = [
            CropPollOptionRead(
                id=option.id, crop_name=option.crop_name, votes=votes_by_option.get(option.id, 0)
            )
            for option in poll.options
        ]
        return cls(
            id=poll.id,
            farm_id=poll.farm_id,
            question=poll.question,
            status=poll.status,
            created_at=poll.created_at,
            options=options,
            total_votes=sum(option.votes for option in options),
        )


class CropPollSearchParams(NearbySearchParams):
    """Query parameters of the search for open polls on nearby farms."""


class CropPollFarm(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_name: str
    city: str
    state: str


class CropPollSearchResult(BaseModel):
    poll: CropPollRead
    farm: CropPollFarm
    distance_miles: float


class CropVoteCreate(BaseModel):
    poll_id: DatabaseId
    option_id: DatabaseId


class CropVoteRead(BaseModel):
    """A customer's own vote."""

    poll_id: int
    option_id: int


class CropVoteResult(CropVoteRead):
    """The vote that was just cast, with the poll's updated counts."""

    poll: CropPollRead
