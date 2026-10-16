from psycopg.errors import UniqueViolation
from sqlalchemy import Subquery, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.application_event import ApplicationEventType
from app.models.farm import Farm
from app.models.grow_offer import CropCommitment, GrowOffer, GrowOfferStatus
from app.models.notification import NotificationType
from app.models.user import User
from app.schemas.grow_offer import (
    CropCommitmentCreate,
    CropCommitmentRead,
    GrowOfferCreate,
    GrowOfferDetail,
    GrowOfferFarm,
    GrowOfferRead,
    GrowOfferSearchParams,
    GrowOfferSearchResult,
)
from app.services.application_events import record_event
from app.services.clock import marketplace_today
from app.services.geo import geography_point, meters_to_miles, miles_to_meters
from app.services.notifications import (
    cancelled_message,
    confirmed_message,
    notify_committed_customers,
)

# Offers a customer can still join.
JOINABLE_STATUSES = (GrowOfferStatus.OPEN, GrowOfferStatus.CONFIRMED)

# Offers a farmer can still call off. Once a crop is growing it is managed
# through its crop journey instead.
CANCELLABLE_STATUSES = (GrowOfferStatus.OPEN, GrowOfferStatus.CONFIRMED)


class HarvestDateInPastError(Exception):
    pass


class GrowOfferNotFoundError(Exception):
    pass


class GrowOfferNotJoinableError(Exception):
    pass


class GrowOfferNotCancellableError(Exception):
    pass


class GrowOfferNotReadyError(Exception):
    """Only an offer whose crop is ready can be marked completed."""


class AlreadyCommittedError(Exception):
    pass


class InsufficientOfferQuantityError(Exception):
    def __init__(self, quantity_remaining: int) -> None:
        super().__init__(quantity_remaining)
        self.quantity_remaining = quantity_remaining


def _progress_by_offer() -> Subquery:
    """Customers and quantity committed to each offer."""
    return (
        select(
            CropCommitment.grow_offer_id,
            func.count(CropCommitment.id).label("committed_customers"),
            func.sum(CropCommitment.quantity).label("committed_quantity"),
        )
        .group_by(CropCommitment.grow_offer_id)
        .subquery()
    )


def _progress_of(db: Session, offer_id: int) -> tuple[int, int]:
    """(customers committed, quantity committed) for one offer."""
    statement = select(
        func.count(CropCommitment.id), func.coalesce(func.sum(CropCommitment.quantity), 0)
    ).where(CropCommitment.grow_offer_id == offer_id)
    committed_customers, committed_quantity = db.execute(statement).one()
    return committed_customers, committed_quantity


def get_grow_offer(db: Session, offer_id: int) -> GrowOffer | None:
    return db.get(GrowOffer, offer_id)


def lock_grow_offer(db: Session, offer_id: int) -> GrowOffer | None:
    """Load an offer and hold a row lock on it until the transaction ends."""
    statement = (
        select(GrowOffer)
        .where(GrowOffer.id == offer_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)


def read_grow_offer(db: Session, offer: GrowOffer) -> GrowOfferRead:
    return GrowOfferRead.from_offer(offer, *_progress_of(db, offer.id))


def create_grow_offer(db: Session, farm: Farm, details: GrowOfferCreate) -> GrowOfferRead:
    if details.expected_harvest_date < marketplace_today():
        raise HarvestDateInPastError
    # GrowOfferCreate has no farm_id or status: the farm comes from the
    # session and every offer starts open.
    offer = GrowOffer(farm_id=farm.id, status=GrowOfferStatus.OPEN, **details.model_dump())
    db.add(offer)
    db.flush()
    record_event(
        db,
        ApplicationEventType.GROW_OFFER_CREATED,
        user_id=farm.owner_id,
        farm_id=farm.id,
        metadata={
            "grow_offer_id": offer.id,
            "crop_name": offer.crop_name,
            "expected_quantity": offer.expected_quantity,
            "unit": offer.unit.value,
            "minimum_customers": offer.minimum_customers,
        },
    )
    db.commit()
    return GrowOfferRead.from_offer(offer, committed_customers=0, committed_quantity=0)


def list_grow_offers_of_farm(db: Session, farm: Farm) -> list[GrowOfferRead]:
    progress = _progress_by_offer()
    statement = (
        select(
            GrowOffer,
            func.coalesce(progress.c.committed_customers, 0),
            func.coalesce(progress.c.committed_quantity, 0),
        )
        .outerjoin(progress, progress.c.grow_offer_id == GrowOffer.id)
        .where(GrowOffer.farm_id == farm.id)
        .order_by(GrowOffer.id.desc())
    )
    return [
        GrowOfferRead.from_offer(offer, committed_customers, committed_quantity)
        for offer, committed_customers, committed_quantity in db.execute(statement)
    ]


def search_grow_offers(db: Session, params: GrowOfferSearchParams) -> list[GrowOfferSearchResult]:
    """Find offers a customer can still join on farms within a radius, soonest harvest first."""
    search_point = geography_point(params.latitude, params.longitude)
    distance_meters = func.ST_Distance(Farm.location, search_point)
    progress = _progress_by_offer()

    statement = (
        select(
            GrowOffer,
            Farm,
            func.coalesce(progress.c.committed_customers, 0),
            func.coalesce(progress.c.committed_quantity, 0),
            distance_meters.label("distance_meters"),
        )
        .join(Farm, GrowOffer.farm_id == Farm.id)
        .outerjoin(progress, progress.c.grow_offer_id == GrowOffer.id)
        .where(GrowOffer.status.in_(JOINABLE_STATUSES))
        .where(GrowOffer.expected_harvest_date >= marketplace_today())
        .where(func.ST_DWithin(Farm.location, search_point, miles_to_meters(params.radius_miles)))
    )
    if params.crop is not None:
        statement = statement.where(GrowOffer.crop_name.icontains(params.crop, autoescape=True))
    statement = statement.order_by(
        GrowOffer.expected_harvest_date, distance_meters.asc(), GrowOffer.id
    ).limit(params.limit)

    return [
        GrowOfferSearchResult(
            offer=GrowOfferRead.from_offer(offer, committed_customers, committed_quantity),
            farm=GrowOfferFarm.model_validate(farm),
            distance_miles=meters_to_miles(row_distance_meters),
        )
        for offer, farm, committed_customers, committed_quantity, row_distance_meters in db.execute(
            statement
        )
    ]


def cancel_grow_offer(db: Session, offer: GrowOffer) -> GrowOfferRead:
    locked_offer = lock_grow_offer(db, offer.id)
    assert locked_offer is not None  # the caller has just loaded it
    if locked_offer.status not in CANCELLABLE_STATUSES:
        raise GrowOfferNotCancellableError
    locked_offer.status = GrowOfferStatus.CANCELLED
    notify_committed_customers(
        db, locked_offer, NotificationType.GROW_OFFER_CANCELLED, cancelled_message(locked_offer)
    )
    db.commit()
    return read_grow_offer(db, locked_offer)


def complete_grow_offer(db: Session, offer: GrowOffer) -> GrowOfferRead:
    """Close an offer whose crop was ready and has been handed over."""
    locked_offer = lock_grow_offer(db, offer.id)
    assert locked_offer is not None  # the caller has just loaded it
    if locked_offer.status is not GrowOfferStatus.READY:
        raise GrowOfferNotReadyError
    locked_offer.status = GrowOfferStatus.COMPLETED
    db.commit()
    return read_grow_offer(db, locked_offer)


def read_grow_offer_with_farm(db: Session, offer: GrowOffer) -> GrowOfferDetail:
    return GrowOfferDetail(
        offer=read_grow_offer(db, offer), farm=GrowOfferFarm.model_validate(offer.farm)
    )


def commit_to_grow_offer(
    db: Session, customer: User, details: CropCommitmentCreate
) -> CropCommitmentRead:
    """Add a customer's commitment and confirm the offer if that reaches its threshold.

    The offer row is locked for the whole operation, so commitments to one
    offer are processed one at a time. Each one therefore counts every
    commitment made before it, including one that committed a moment earlier,
    and the commitment that reaches minimum_customers is the one that moves
    the offer from OPEN to CONFIRMED. Without the lock, two customers
    committing together could each count only themselves and leave an offer
    that has met its threshold still open.

    The commitment and the status change are saved in one transaction: the
    offer is never confirmed without the commitment that confirmed it.
    """
    offer = lock_grow_offer(db, details.grow_offer_id)
    if offer is None:
        raise GrowOfferNotFoundError
    if offer.status not in JOINABLE_STATUSES:
        raise GrowOfferNotJoinableError

    already_committed = db.scalar(
        select(CropCommitment.id).where(
            CropCommitment.grow_offer_id == offer.id,
            CropCommitment.customer_id == customer.id,
        )
    )
    if already_committed is not None:
        raise AlreadyCommittedError

    committed_customers, committed_quantity = _progress_of(db, offer.id)
    quantity_remaining = offer.expected_quantity - committed_quantity
    if details.quantity > quantity_remaining:
        raise InsufficientOfferQuantityError(quantity_remaining)

    commitment = CropCommitment(
        grow_offer_id=offer.id, customer_id=customer.id, quantity=details.quantity
    )
    db.add(commitment)
    committed_customers += 1
    committed_quantity += details.quantity

    try:
        # Flushing first writes the new commitment, so the customer whose
        # commitment confirms the offer is notified along with the rest and
        # the commitment has an id for its event.
        db.flush()
        confirms_offer = (
            offer.status is GrowOfferStatus.OPEN and committed_customers >= offer.minimum_customers
        )
        if confirms_offer:
            offer.status = GrowOfferStatus.CONFIRMED
            notify_committed_customers(
                db, offer, NotificationType.GROW_OFFER_CONFIRMED, confirmed_message(offer)
            )
        record_event(
            db,
            ApplicationEventType.CROP_COMMITTED,
            user_id=customer.id,
            farm_id=offer.farm_id,
            metadata={
                "crop_commitment_id": commitment.id,
                "grow_offer_id": offer.id,
                "crop_name": offer.crop_name,
                "quantity": details.quantity,
                "confirmed_offer": confirms_offer,
            },
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # The unique constraint is the final guard against a second
        # commitment from the same customer.
        if isinstance(error.orig, UniqueViolation):
            raise AlreadyCommittedError from error
        raise
    return CropCommitmentRead.from_commitment(commitment, committed_customers, committed_quantity)


def list_commitments_of_customer(db: Session, customer: User) -> list[CropCommitmentRead]:
    progress = _progress_by_offer()
    statement = (
        select(
            CropCommitment,
            func.coalesce(progress.c.committed_customers, 0),
            func.coalesce(progress.c.committed_quantity, 0),
        )
        .outerjoin(progress, progress.c.grow_offer_id == CropCommitment.grow_offer_id)
        .where(CropCommitment.customer_id == customer.id)
        .options(joinedload(CropCommitment.grow_offer).joinedload(GrowOffer.farm))
        .order_by(CropCommitment.id.desc())
    )
    return [
        CropCommitmentRead.from_commitment(commitment, committed_customers, committed_quantity)
        for commitment, committed_customers, committed_quantity in db.execute(statement)
    ]
