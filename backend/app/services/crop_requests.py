from psycopg.errors import UniqueViolation
from sqlalchemy import ColumnElement, case, distinct, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.crop_request import CropRequest, CropRequestStatus, RequestFrequency
from app.models.farm import Farm
from app.models.grow_offer import CropCommitment, GrowOffer, GrowOfferStatus
from app.models.user import User
from app.schemas.crop_request import CropDemand, CropRequestCreate, CropRequestRead
from app.services.geo import METERS_PER_MILE

# A monthly request contributes this share of its quantity to each week.
MONTHLY_TO_WEEKLY = 12 / 52

# Offers that are still on their way to a harvest. A customer who has joined
# one of these for a crop is already being served for that crop.
ACTIVE_GROW_OFFER_STATUSES = (
    GrowOfferStatus.OPEN,
    GrowOfferStatus.CONFIRMED,
    GrowOfferStatus.GROWING,
    GrowOfferStatus.READY,
)


class DuplicateCropRequestError(Exception):
    """The customer already has an open request for this crop."""


class CropRequestNotFoundError(Exception):
    pass


class CropRequestNotOpenError(Exception):
    pass


def _is_covered_by_commitment() -> ColumnElement[bool]:
    """Whether the request's customer has joined an active grow offer for the same crop.

    This is worked out from commitments each time rather than stored on the
    request, so it can never fall out of step: joining an offer covers the
    request, and the offer being cancelled uncovers it again.
    """
    return (
        select(CropCommitment.id)
        .join(GrowOffer, CropCommitment.grow_offer_id == GrowOffer.id)
        .where(
            CropCommitment.customer_id == CropRequest.customer_id,
            GrowOffer.crop_name == CropRequest.crop_name,
            GrowOffer.status.in_(ACTIVE_GROW_OFFER_STATUSES),
        )
        .exists()
    )


def _to_read(request: CropRequest, covered_by_commitment: bool) -> CropRequestRead:
    return CropRequestRead(
        id=request.id,
        crop_name=request.crop_name,
        quantity=request.quantity,
        unit=request.unit,
        frequency=request.frequency,
        latitude=request.latitude,
        longitude=request.longitude,
        radius_miles=request.radius_miles,
        preferred_season=request.preferred_season,
        notes=request.notes,
        status=request.status,
        created_at=request.created_at,
        covered_by_commitment=covered_by_commitment,
    )


def create_crop_request(db: Session, customer: User, details: CropRequestCreate) -> CropRequestRead:
    # CropRequestCreate has no customer_id, so the customer always comes from the session.
    request = CropRequest(
        customer_id=customer.id, status=CropRequestStatus.OPEN, **details.model_dump()
    )
    db.add(request)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # The partial unique index on (customer, crop) for open requests is
        # the source of truth, so two simultaneous requests cannot both pass.
        if isinstance(error.orig, UniqueViolation):
            raise DuplicateCropRequestError(details.crop_name) from error
        raise
    covered = db.scalar(select(_is_covered_by_commitment()).where(CropRequest.id == request.id))
    return _to_read(request, bool(covered))


def list_crop_requests_of_customer(db: Session, customer: User) -> list[CropRequestRead]:
    statement = (
        select(CropRequest, _is_covered_by_commitment())
        .where(CropRequest.customer_id == customer.id)
        .order_by(CropRequest.id.desc())
    )
    return [_to_read(request, covered) for request, covered in db.execute(statement)]


def cancel_crop_request(db: Session, customer: User, request_id: int) -> CropRequestRead:
    """Withdraw one of the customer's own open requests.

    A request that belongs to someone else is reported as not found, so the
    endpoint does not confirm which request ids exist.
    """
    statement = (
        select(CropRequest)
        .where(CropRequest.id == request_id, CropRequest.customer_id == customer.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    request = db.scalar(statement)
    if request is None:
        raise CropRequestNotFoundError
    if request.status is not CropRequestStatus.OPEN:
        raise CropRequestNotOpenError
    request.status = CropRequestStatus.CANCELLED
    db.commit()
    return _to_read(request, covered_by_commitment=False)


def summarize_demand_near_farm(db: Session, farm: Farm) -> list[CropDemand]:
    """Add up open crop requests whose travel radius reaches the farm.

    A request counts when the farm lies within the distance its customer is
    willing to travel. PostGIS makes that comparison, using the request's
    rounded location, and only the totals leave the database: no row here
    describes an individual request or customer.
    """
    weekly_share = case(
        (CropRequest.frequency == RequestFrequency.WEEKLY, 1.0),
        (CropRequest.frequency == RequestFrequency.MONTHLY, MONTHLY_TO_WEEKLY),
        else_=0.0,
    )
    one_time_quantity = case(
        (CropRequest.frequency == RequestFrequency.ONE_TIME, CropRequest.quantity), else_=0
    )
    customers_interested = func.count(distinct(CropRequest.customer_id))

    statement = (
        select(
            CropRequest.crop_name,
            CropRequest.unit,
            customers_interested,
            func.sum(CropRequest.quantity * weekly_share),
            func.sum(one_time_quantity),
        )
        .join(Farm, Farm.id == farm.id)
        .where(CropRequest.status == CropRequestStatus.OPEN)
        .where(
            func.ST_DWithin(
                CropRequest.approximate_location,
                Farm.location,
                CropRequest.radius_miles * METERS_PER_MILE,
            )
        )
        .where(~_is_covered_by_commitment())
        .group_by(CropRequest.crop_name, CropRequest.unit)
        .order_by(customers_interested.desc(), CropRequest.crop_name, CropRequest.unit)
    )
    return [
        CropDemand(
            crop_name=crop_name,
            unit=unit,
            customers_interested=customers,
            estimated_weekly_quantity=round(float(weekly_quantity), 1),
            one_time_quantity=int(one_time),
        )
        for crop_name, unit, customers, weekly_quantity, one_time in db.execute(statement)
    ]
