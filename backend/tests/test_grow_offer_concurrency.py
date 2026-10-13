"""Commitments made at the same moment, on separate database connections.

Like the reservation concurrency tests, these commit for real. Each thread
opens its connection and loads its customer first, then waits at a barrier so
that both reach the commitment code together. Run against the code with the
grow offer row lock removed, the threshold and quantity tests fail.
"""

from sqlalchemy import func, select

from app.models.grow_offer import CropCommitment, GrowOffer, GrowOfferStatus
from app.models.user import User, UserRole
from app.schemas.grow_offer import CropCommitmentCreate
from app.services.grow_offers import (
    AlreadyCommittedError,
    InsufficientOfferQuantityError,
    commit_to_grow_offer,
)
from tests.concurrency import Action, SessionFactory, WaitForStart, run_together
from tests.helpers import create_farmer_with_farm, create_grow_offer, create_user


def committing(
    session_factory: SessionFactory, customer_id: int, offer_id: int, quantity: int
) -> Action:
    """An action in which one customer commits to an offer."""

    def action(wait_for_start: WaitForStart) -> str:
        with session_factory() as session:
            customer = session.get(User, customer_id)
            assert customer is not None
            details = CropCommitmentCreate(grow_offer_id=offer_id, quantity=quantity)
            wait_for_start()
            try:
                commit_to_grow_offer(session, customer, details)
            except InsufficientOfferQuantityError:
                return "refused: not enough left"
            except AlreadyCommittedError:
                return "refused: already committed"
            return "committed"

    return action


def test_offer_is_confirmed_when_the_last_two_customers_commit_at_once(
    committing_session_factory: SessionFactory,
) -> None:
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        offer_id = create_grow_offer(setup, farm, minimum_customers=2).id
        customer_ids = [
            create_user(setup, role=UserRole.CUSTOMER, email=f"customer-{number}@example.com").id
            for number in (1, 2)
        ]

    outcomes = run_together(
        [
            committing(committing_session_factory, customer_id, offer_id, quantity=5)
            for customer_id in customer_ids
        ]
    )

    assert outcomes == ["committed", "committed"]
    with committing_session_factory() as check:
        offer = check.get(GrowOffer, offer_id)
        assert offer is not None
        assert check.scalar(select(func.count()).select_from(CropCommitment)) == 2
        # Each thread on its own would count one customer and leave the offer open.
        assert offer.status is GrowOfferStatus.CONFIRMED


def test_two_customers_cannot_both_commit_to_the_last_of_the_harvest(
    committing_session_factory: SessionFactory,
) -> None:
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        offer_id = create_grow_offer(setup, farm, expected_quantity=10).id
        customer_ids = [
            create_user(setup, role=UserRole.CUSTOMER, email=f"customer-{number}@example.com").id
            for number in (1, 2)
        ]

    outcomes = run_together(
        [
            committing(committing_session_factory, customer_id, offer_id, quantity=6)
            for customer_id in customer_ids
        ]
    )

    assert outcomes == ["committed", "refused: not enough left"]
    with committing_session_factory() as check:
        offer = check.get(GrowOffer, offer_id)
        assert offer is not None
        committed_quantity = check.scalar(select(func.sum(CropCommitment.quantity)))
        assert committed_quantity == 6
        assert committed_quantity <= offer.expected_quantity


def test_one_customer_submitting_twice_at_once_gets_one_commitment(
    committing_session_factory: SessionFactory,
) -> None:
    with committing_session_factory() as setup:
        farm = create_farmer_with_farm(setup, "farmer@example.com")
        offer_id = create_grow_offer(setup, farm, minimum_customers=2).id
        customer_id = create_user(
            setup, role=UserRole.CUSTOMER, email="customer@example.com"
        ).id

    outcomes = run_together(
        [committing(committing_session_factory, customer_id, offer_id, quantity=5) for _ in range(2)]
    )

    assert outcomes == ["committed", "refused: already committed"]
    with committing_session_factory() as check:
        offer = check.get(GrowOffer, offer_id)
        assert offer is not None
        assert check.scalar(select(func.count()).select_from(CropCommitment)) == 1
        # One customer twice is still one customer, so the threshold of two is not met.
        assert offer.status is GrowOfferStatus.OPEN
