from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentCustomer, CurrentFarmer, CurrentUser
from app.dependencies.path_params import ResourceId
from app.dependencies.reservations import (
    invalid_status_transition,
    resolve_reservation_actor,
    status_change_not_permitted,
)
from app.schemas.reservation import (
    ProductReservationCreate,
    ProductReservationRead,
    ReservationStatusUpdate,
)
from app.services.farms import get_farm_owned_by
from app.services.reservation_status import (
    InvalidStatusTransitionError,
    StatusChangeNotPermittedError,
)
from app.services.reservations import (
    InsufficientStockError,
    PickupDateInPastError,
    ProductNotFoundError,
    ProductNotReservableError,
    change_product_reservation_status,
    create_product_reservation,
    get_product_reservation,
    list_reservations_for_farm,
    list_reservations_of_customer,
)

router = APIRouter(prefix="/reservations", tags=["product reservations"])


@router.post("", response_model=ProductReservationRead, status_code=status.HTTP_201_CREATED)
def reserve_product(
    details: ProductReservationCreate, customer: CurrentCustomer, db: DatabaseSession
) -> ProductReservationRead:
    try:
        reservation = create_product_reservation(db, customer, details)
    except PickupDateInPastError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Pickup date cannot be in the past",
        ) from None
    except ProductNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        ) from None
    except ProductNotReservableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This product is not available to reserve right now",
        ) from None
    except InsufficientStockError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only {error.quantity_available} available",
        ) from None
    return ProductReservationRead.from_reservation(reservation)


@router.get("/mine", response_model=list[ProductReservationRead])
def list_my_reservations(
    customer: CurrentCustomer, db: DatabaseSession
) -> list[ProductReservationRead]:
    return [
        ProductReservationRead.from_reservation(reservation)
        for reservation in list_reservations_of_customer(db, customer)
    ]


@router.get("/farm", response_model=list[ProductReservationRead])
def list_reservations_for_my_farm(
    farmer: CurrentFarmer, db: DatabaseSession
) -> list[ProductReservationRead]:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        return []
    return [
        ProductReservationRead.from_reservation(reservation)
        for reservation in list_reservations_for_farm(db, farm)
    ]


@router.patch("/{reservation_id}/status", response_model=ProductReservationRead)
def update_reservation_status(
    reservation_id: ResourceId,
    update: ReservationStatusUpdate,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> ProductReservationRead:
    reservation = get_product_reservation(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")
    actor = resolve_reservation_actor(
        current_user, reservation.customer_id, reservation.product.farm
    )
    try:
        reservation = change_product_reservation_status(db, reservation, update.status, actor)
    except StatusChangeNotPermittedError:
        raise status_change_not_permitted(update.status) from None
    except InvalidStatusTransitionError as error:
        raise invalid_status_transition(error) from None
    return ProductReservationRead.from_reservation(reservation)
