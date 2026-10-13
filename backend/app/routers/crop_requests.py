from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentCustomer
from app.dependencies.path_params import ResourceId
from app.schemas.crop_request import CropRequestCreate, CropRequestRead
from app.services.crop_requests import (
    CropRequestNotFoundError,
    CropRequestNotOpenError,
    DuplicateCropRequestError,
    cancel_crop_request,
    create_crop_request,
    list_crop_requests_of_customer,
)

router = APIRouter(prefix="/crop-requests", tags=["crop requests"])


@router.post("", response_model=CropRequestRead, status_code=status.HTTP_201_CREATED)
def request_crop(
    details: CropRequestCreate, customer: CurrentCustomer, db: DatabaseSession
) -> CropRequestRead:
    try:
        return create_crop_request(db, customer, details)
    except DuplicateCropRequestError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an open request for {details.crop_name}",
        ) from None


@router.get("/mine", response_model=list[CropRequestRead])
def list_my_crop_requests(customer: CurrentCustomer, db: DatabaseSession) -> list[CropRequestRead]:
    return list_crop_requests_of_customer(db, customer)


@router.post("/{request_id}/cancel", response_model=CropRequestRead)
def cancel_my_crop_request(
    request_id: ResourceId, customer: CurrentCustomer, db: DatabaseSession
) -> CropRequestRead:
    try:
        return cancel_crop_request(db, customer, request_id)
    except CropRequestNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Crop request not found"
        ) from None
    except CropRequestNotOpenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only an open crop request can be cancelled",
        ) from None
