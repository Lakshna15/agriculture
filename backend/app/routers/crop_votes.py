from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentCustomer
from app.schemas.crop_poll import CropVoteCreate, CropVoteRead, CropVoteResult
from app.services.crop_polls import (
    AlreadyVotedError,
    CropPollClosedError,
    CropPollNotFoundError,
    CropPollOptionNotFoundError,
    cast_vote,
    list_votes_of_customer,
)

router = APIRouter(prefix="/crop-votes", tags=["crop polls"])


@router.post("", response_model=CropVoteResult, status_code=status.HTTP_201_CREATED)
def vote(details: CropVoteCreate, customer: CurrentCustomer, db: DatabaseSession) -> CropVoteResult:
    try:
        return cast_vote(db, customer, details)
    except CropPollNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crop poll not found"
        ) from None
    except CropPollOptionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That option is not part of this crop poll",
        ) from None
    except CropPollClosedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This crop poll is closed"
        ) from None
    except AlreadyVotedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already voted in this crop poll",
        ) from None


@router.get("/mine", response_model=list[CropVoteRead])
def list_my_votes(customer: CurrentCustomer, db: DatabaseSession) -> list[CropVoteRead]:
    return list_votes_of_customer(db, customer)
