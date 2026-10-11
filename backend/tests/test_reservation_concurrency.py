"""Reservations made at the same moment, on separate database connections.

These tests commit for real, because a row lock only matters between
transactions. Each thread first opens its own connection and loads what it
needs, then waits at a barrier, so that both reach the reservation code at the
same instant with nothing left to set up. Run against the code with its row
locks removed, all three tests fail.
"""

import threading
from collections.abc import Callable
from datetime import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.event import EventReservation, FarmEvent
from app.models.product import InventoryHistory, Product
from app.models.reservation import ProductReservation, ReservationStatus
from app.models.user import User, UserRole
from app.schemas.event import EventReservationCreate
from app.schemas.reservation import ProductReservationCreate
from app.services.event_reservations import EventFullError, create_event_reservation
from app.services.reservation_status import InvalidStatusTransitionError, ReservationActor
from app.services.reservations import (
    InsufficientStockError,
    change_product_reservation_status,
    create_product_reservation,
)
from tests.helpers import (
    create_event,
    create_farmer_with_farm,
    create_product,
    create_user,
    days_from_today,
)

SessionFactory = sessionmaker[Session]

# An action receives a function to call once it is connected and ready. That
# call blocks until every other action is ready too.
WaitForStart = Callable[[], None]
Action = Callable[[WaitForStart], str]


def run_together(actions: list[Action]) -> list[str]:
    """Run each action on its own thread and release them all at the same instant."""
    barrier = threading.Barrier(len(actions))
    outcomes: list[str] = []

    def run(action: Action) -> None:
        outcomes.append(action(lambda: barrier.wait(timeout=10)))

    threads = [threading.Thread(target=run, args=(action,)) for action in actions]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert not any(thread.is_alive() for thread in threads), "a reservation is deadlocked"
    assert len(outcomes) == len(actions), "a thread ended without reporting an outcome"
    return sorted(outcomes)


def test_two_customers_cannot_both_reserve_the_last_units(
    committing_session_factory: SessionFactory,
) -> None:
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        product_id = create_product(setup, farm, quantity_available=5).id
        customer_ids = [
            create_user(setup, role=UserRole.CUSTOMER, email=f"customer-{number}@example.com").id
            for number in (1, 2)
        ]

    def reserve_four_units(customer_id: int, wait_for_start: WaitForStart) -> str:
        with committing_session_factory() as session:
            customer = session.get(User, customer_id)
            assert customer is not None
            details = ProductReservationCreate(
                product_id=product_id,
                quantity=4,
                pickup_date=days_from_today(1),
                pickup_time=time(10, 0),
            )
            wait_for_start()
            try:
                create_product_reservation(session, customer, details)
            except InsufficientStockError:
                return "refused"
            return "reserved"

    outcomes = run_together(
        [
            lambda wait_for_start, customer_id=customer_id: reserve_four_units(
                customer_id, wait_for_start
            )
            for customer_id in customer_ids
        ]
    )

    assert outcomes == ["refused", "reserved"]
    with committing_session_factory() as check:
        product = check.get(Product, product_id)
        assert product is not None
        assert product.quantity_available == 1
        assert check.scalar(select(func.count()).select_from(ProductReservation)) == 1
        history = check.scalars(select(InventoryHistory)).all()
        assert [(row.previous_quantity, row.new_quantity) for row in history] == [(5, 1)]


def test_two_parties_cannot_both_take_the_last_places_at_an_event(
    committing_session_factory: SessionFactory,
) -> None:
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        event_id = create_event(setup, farm, capacity=10).id
        customer_ids = [
            create_user(setup, role=UserRole.CUSTOMER, email=f"customer-{number}@example.com").id
            for number in (1, 2)
        ]

    def reserve_six_places(customer_id: int, wait_for_start: WaitForStart) -> str:
        with committing_session_factory() as session:
            customer = session.get(User, customer_id)
            assert customer is not None
            details = EventReservationCreate(event_id=event_id, party_size=6)
            wait_for_start()
            try:
                create_event_reservation(session, customer, details)
            except EventFullError:
                return "refused"
            return "reserved"

    outcomes = run_together(
        [
            lambda wait_for_start, customer_id=customer_id: reserve_six_places(
                customer_id, wait_for_start
            )
            for customer_id in customer_ids
        ]
    )

    assert outcomes == ["refused", "reserved"]
    with committing_session_factory() as check:
        event = check.get(FarmEvent, event_id)
        assert event is not None
        booked = check.scalar(select(func.sum(EventReservation.party_size)))
        assert booked == 6
        assert booked <= event.capacity


def test_cancelling_from_both_sides_at_once_returns_stock_only_once(
    committing_session_factory: SessionFactory,
) -> None:
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        product_id = create_product(setup, farm, quantity_available=10).id
        customer = create_user(setup, role=UserRole.CUSTOMER, email="customer@example.com")
        reservation_id = create_product_reservation(
            setup,
            customer,
            ProductReservationCreate(
                product_id=product_id,
                quantity=4,
                pickup_date=days_from_today(1),
                pickup_time=time(10, 0),
            ),
        ).id

    def cancel_as(actor: ReservationActor, wait_for_start: WaitForStart) -> str:
        with committing_session_factory() as session:
            reservation = session.get(ProductReservation, reservation_id)
            assert reservation is not None
            wait_for_start()
            try:
                change_product_reservation_status(
                    session, reservation, ReservationStatus.CANCELLED, actor
                )
            except InvalidStatusTransitionError:
                return "already cancelled"
            return "cancelled"

    outcomes = run_together(
        [
            lambda wait_for_start: cancel_as(ReservationActor.CUSTOMER, wait_for_start),
            lambda wait_for_start: cancel_as(ReservationActor.FARMER, wait_for_start),
        ]
    )

    assert outcomes == ["already cancelled", "cancelled"]
    with committing_session_factory() as check:
        product = check.get(Product, product_id)
        assert product is not None
        assert product.quantity_available == 10
        history = check.scalars(select(InventoryHistory).order_by(InventoryHistory.id)).all()
        # Deducted once when reserved and returned once when cancelled.
        assert [(row.previous_quantity, row.new_quantity) for row in history] == [(10, 6), (6, 10)]
