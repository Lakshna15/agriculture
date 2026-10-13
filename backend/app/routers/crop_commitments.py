from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentCustomer
from app.schemas.grow_offer import CropCommitmentCreate, CropCommitmentRead
from app.services.grow_offers import (
    AlreadyCommittedError,
    GrowOfferNotFoundError,
    GrowOfferNotJoinableError,
    InsufficientOfferQuantityError,
    commit_to_grow_offer,
    list_commitments_of_customer,
)

router = APIRouter(prefix="/crop-commitments", tags=["crop commitments"])


@router.post("", response_model=CropCommitmentRead, status_code=status.HTTP_201_CREATED)
def join_grow_offer(
    details: CropCommitmentCreate, customer: CurrentCustomer, db: DatabaseSession
) -> CropCommitmentRead:
    try:
        return commit_to_grow_offer(db, customer, details)
    except GrowOfferNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Grow offer not found"
        ) from None
    except GrowOfferNotJoinableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This grow offer is no longer accepting commitments",
        ) from None
    except AlreadyCommittedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already committed to this grow offer",
        ) from None
    except InsufficientOfferQuantityError as error:
        detail = (
            "This grow offer is fully committed"
            if error.quantity_remaining <= 0
            else f"Only {error.quantity_remaining} left in this grow offer"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from None


@router.get("/mine", response_model=list[CropCommitmentRead])
def list_my_commitments(
    customer: CurrentCustomer, db: DatabaseSession
) -> list[CropCommitmentRead]:
    return list_commitments_of_customer(db, customer)
