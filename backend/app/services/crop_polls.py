from psycopg.errors import UniqueViolation
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.crop_poll import CropPoll, CropPollOption, CropPollStatus, CropVote
from app.models.farm import Farm
from app.models.user import User
from app.schemas.crop_poll import (
    CropPollCreate,
    CropPollFarm,
    CropPollRead,
    CropPollSearchParams,
    CropPollSearchResult,
    CropVoteCreate,
    CropVoteRead,
    CropVoteResult,
)
from app.services.geo import geography_point, meters_to_miles, miles_to_meters


class CropPollNotFoundError(Exception):
    pass


class CropPollClosedError(Exception):
    pass


class CropPollOptionNotFoundError(Exception):
    """The option does not exist or belongs to a different poll."""


class AlreadyVotedError(Exception):
    pass


def _votes_by_option(db: Session, poll_ids: list[int]) -> dict[int, int]:
    """Vote counts keyed by option id, for the given polls."""
    if not poll_ids:
        return {}
    statement = (
        select(CropVote.option_id, func.count(CropVote.id))
        .where(CropVote.poll_id.in_(poll_ids))
        .group_by(CropVote.option_id)
    )
    return {option_id: votes for option_id, votes in db.execute(statement)}


def read_crop_poll(db: Session, poll: CropPoll) -> CropPollRead:
    return CropPollRead.from_poll(poll, _votes_by_option(db, [poll.id]))


def get_crop_poll(db: Session, poll_id: int) -> CropPoll | None:
    statement = select(CropPoll).where(CropPoll.id == poll_id).options(selectinload(CropPoll.options))
    return db.scalar(statement)


def create_crop_poll(db: Session, farm: Farm, details: CropPollCreate) -> CropPollRead:
    # CropPollCreate has no farm_id or status: the farm comes from the
    # session and every poll starts open.
    poll = CropPoll(
        farm_id=farm.id,
        question=details.question,
        status=CropPollStatus.OPEN,
        options=[CropPollOption(crop_name=crop_name) for crop_name in details.options],
    )
    db.add(poll)
    db.commit()
    return CropPollRead.from_poll(poll, votes_by_option={})


def list_crop_polls_of_farm(db: Session, farm: Farm) -> list[CropPollRead]:
    statement = (
        select(CropPoll)
        .where(CropPoll.farm_id == farm.id)
        .options(selectinload(CropPoll.options))
        .order_by(CropPoll.id.desc())
    )
    polls = list(db.scalars(statement))
    votes_by_option = _votes_by_option(db, [poll.id for poll in polls])
    return [CropPollRead.from_poll(poll, votes_by_option) for poll in polls]


def close_crop_poll(db: Session, poll: CropPoll) -> CropPollRead:
    if poll.status is CropPollStatus.CLOSED:
        raise CropPollClosedError
    poll.status = CropPollStatus.CLOSED
    db.commit()
    return read_crop_poll(db, poll)


def search_crop_polls(db: Session, params: CropPollSearchParams) -> list[CropPollSearchResult]:
    """Find open polls on farms within a radius of a point, newest first."""
    search_point = geography_point(params.latitude, params.longitude)
    distance_meters = func.ST_Distance(Farm.location, search_point)

    statement = (
        select(CropPoll, Farm, distance_meters.label("distance_meters"))
        .join(Farm, CropPoll.farm_id == Farm.id)
        .where(CropPoll.status == CropPollStatus.OPEN)
        .where(func.ST_DWithin(Farm.location, search_point, miles_to_meters(params.radius_miles)))
        .options(selectinload(CropPoll.options))
        .order_by(CropPoll.id.desc())
        .limit(params.limit)
    )
    rows = db.execute(statement).all()
    votes_by_option = _votes_by_option(db, [poll.id for poll, _farm, _distance in rows])
    return [
        CropPollSearchResult(
            poll=CropPollRead.from_poll(poll, votes_by_option),
            farm=CropPollFarm.model_validate(farm),
            distance_miles=meters_to_miles(row_distance_meters),
        )
        for poll, farm, row_distance_meters in rows
    ]


def cast_vote(db: Session, customer: User, details: CropVoteCreate) -> CropVoteResult:
    poll = get_crop_poll(db, details.poll_id)
    if poll is None:
        raise CropPollNotFoundError
    if poll.status is not CropPollStatus.OPEN:
        raise CropPollClosedError
    if details.option_id not in {option.id for option in poll.options}:
        raise CropPollOptionNotFoundError

    db.add(CropVote(poll_id=poll.id, option_id=details.option_id, customer_id=customer.id))
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        # The unique constraint on (poll, customer) is the source of truth, so
        # a customer who submits twice at the same moment still gets one vote.
        if isinstance(error.orig, UniqueViolation):
            raise AlreadyVotedError from error
        raise
    return CropVoteResult(
        poll_id=poll.id, option_id=details.option_id, poll=read_crop_poll(db, poll)
    )


def list_votes_of_customer(db: Session, customer: User) -> list[CropVoteRead]:
    statement = (
        select(CropVote.poll_id, CropVote.option_id)
        .where(CropVote.customer_id == customer.id)
        .order_by(CropVote.id.desc())
    )
    return [
        CropVoteRead(poll_id=poll_id, option_id=option_id)
        for poll_id, option_id in db.execute(statement)
    ]
