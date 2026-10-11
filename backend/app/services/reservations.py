from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import Select

from app.models.farm import Farm
from app.models.product import Product
from app.models.reservation import ProductReservation, ReservationStatus
from app.models.user import User
from app.schemas.reservation import ProductReservationCreate
from app.services.clock import marketplace_today
from app.services.products import change_product_quantity, lock_product
from app.services.reservation_status import ReservationActor, check_status_change


class ProductNotFoundError(Exception):
    pass


class ProductNotReservableError(Exception):
    """The product is hidden by its farmer or outside its availability dates."""


class PickupDateInPastError(Exception):
    pass


class InsufficientStockError(Exception):
    def __init__(self, quantity_available: int) -> None:
        super().__init__(quantity_available)
        self.quantity_available = quantity_available


def _with_details(statement: Select) -> Select:
    """Load the product, its farm and the customer together with each reservation."""
    return statement.options(
        joinedload(ProductReservation.product).joinedload(Product.farm),
        joinedload(ProductReservation.customer),
    )


def _is_offered_on(product: Product, day: date) -> bool:
    return (
        product.active
        and (product.available_from is None or product.available_from <= day)
        and (product.available_until is None or product.available_until >= day)
    )


def _lock_reservation(db: Session, reservation_id: int) -> None:
    """Hold a row lock on a reservation and bring the session's copy up to date.

    A plain single-table SELECT is used on purpose: PostgreSQL cannot lock
    through the outer joins that loading the related product and customer adds.
    """
    # scalar() reads the row, which is what refreshes the copy already in the session.
    db.scalar(
        select(ProductReservation)
        .where(ProductReservation.id == reservation_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_product_reservation(db: Session, reservation_id: int) -> ProductReservation | None:
    statement = _with_details(
        select(ProductReservation).where(ProductReservation.id == reservation_id)
    )
    return db.scalar(statement)


def list_reservations_of_customer(db: Session, customer: User) -> list[ProductReservation]:
    statement = _with_details(
        select(ProductReservation)
        .where(ProductReservation.customer_id == customer.id)
        .order_by(ProductReservation.id.desc())
    )
    return list(db.scalars(statement))


def list_reservations_for_farm(db: Session, farm: Farm) -> list[ProductReservation]:
    statement = _with_details(
        select(ProductReservation)
        .join(Product, ProductReservation.product_id == Product.id)
        .where(Product.farm_id == farm.id)
        .order_by(ProductReservation.pickup_date, ProductReservation.pickup_time)
    )
    return list(db.scalars(statement))


def create_product_reservation(
    db: Session, customer: User, details: ProductReservationCreate
) -> ProductReservation:
    """Reserve stock for a customer.

    The product row is locked first. A second reservation of the same product
    then waits until this one commits and sees the reduced stock, so two
    customers can never both be given the last units. The stock deduction, its
    history row and the reservation are saved in one transaction.
    """
    today = marketplace_today()
    if details.pickup_date < today:
        raise PickupDateInPastError

    product = lock_product(db, details.product_id)
    if product is None:
        raise ProductNotFoundError
    if not _is_offered_on(product, today):
        raise ProductNotReservableError
    if details.quantity > product.quantity_available:
        raise InsufficientStockError(product.quantity_available)

    change_product_quantity(db, product, product.quantity_available - details.quantity)
    reservation = ProductReservation(
        customer_id=customer.id,
        product_id=product.id,
        quantity=details.quantity,
        pickup_date=details.pickup_date,
        pickup_time=details.pickup_time,
        status=ReservationStatus.PENDING,
    )
    db.add(reservation)
    db.commit()
    return reservation


def change_product_reservation_status(
    db: Session,
    reservation: ProductReservation,
    new_status: ReservationStatus,
    actor: ReservationActor,
) -> ProductReservation:
    """Move a reservation to a new status and keep stock in step.

    Cancelling returns the reserved quantity to the product. Completing does
    not touch stock, because it was already deducted when the reservation was
    made.
    """
    # The reservation is locked before its status is checked. Without the lock
    # two simultaneous cancellations could both see it as active and each
    # return its quantity to stock.
    _lock_reservation(db, reservation.id)
    check_status_change(actor, reservation.status, new_status)

    if new_status is ReservationStatus.CANCELLED:
        product = lock_product(db, reservation.product_id)
        assert product is not None  # guaranteed by the foreign key
        change_product_quantity(db, product, product.quantity_available + reservation.quantity)

    reservation.status = new_status
    db.commit()
    db.refresh(reservation)
    return reservation
