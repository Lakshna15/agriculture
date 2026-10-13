from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.crop_update import CropStage, CropUpdate
from app.models.grow_offer import GrowOffer, GrowOfferStatus
from app.models.notification import NotificationType
from app.schemas.crop_update import CropUpdateCreate
from app.services.grow_offers import lock_grow_offer
from app.services.notifications import (
    crop_ready_message,
    crop_update_message,
    notify_committed_customers,
)

# Position of each stage in the growing order, taken from the enum's declaration order.
_STAGE_ORDER = {stage: position for position, stage in enumerate(CropStage)}

# Offers whose crop journey is over.
_CLOSED_STATUSES = (GrowOfferStatus.COMPLETED, GrowOfferStatus.CANCELLED)

# Stages that mean the crop is in the ground.
_GROWING_STAGES = (
    CropStage.PLANTED,
    CropStage.GERMINATED,
    CropStage.GROWING,
    CropStage.FLOWERING,
    CropStage.HARVEST_SOON,
)


class GrowOfferClosedError(Exception):
    """The offer is completed or cancelled and takes no more updates."""


class OfferNotConfirmedError(Exception):
    """Only a PLANNED update can be posted before enough customers have committed."""


class StageRegressionError(Exception):
    def __init__(self, latest_stage: CropStage) -> None:
        super().__init__(latest_stage)
        self.latest_stage = latest_stage


def list_crop_updates(db: Session, offer: GrowOffer) -> list[CropUpdate]:
    """An offer's crop journey in the order it happened."""
    statement = (
        select(CropUpdate)
        .where(CropUpdate.grow_offer_id == offer.id)
        .order_by(CropUpdate.created_at, CropUpdate.id)
    )
    return list(db.scalars(statement))


def post_crop_update(db: Session, offer: GrowOffer, details: CropUpdateCreate) -> CropUpdate:
    """Add an entry to an offer's crop journey and move the offer along with it.

    The stage of an update drives the offer's status, so the two always agree:

    - a stage from PLANTED to HARVEST_SOON moves a CONFIRMED offer to GROWING;
    - READY moves a CONFIRMED or GROWING offer to READY.

    Every committed customer is notified, with a dedicated message when the
    crop becomes ready. The update, the status change and the notifications
    are saved in one transaction, under a lock on the offer so that two
    updates posted together are checked against each other.
    """
    locked_offer = lock_grow_offer(db, offer.id)
    assert locked_offer is not None  # the caller has just loaded it

    if locked_offer.status in _CLOSED_STATUSES:
        raise GrowOfferClosedError
    # An open offer has not reached its minimum customers, so the farmer has
    # not yet agreed to grow the crop. It can be planned, but not planted.
    if locked_offer.status is GrowOfferStatus.OPEN and details.stage is not CropStage.PLANNED:
        raise OfferNotConfirmedError

    latest_stage = db.scalar(
        select(CropUpdate.stage)
        .where(CropUpdate.grow_offer_id == locked_offer.id)
        .order_by(CropUpdate.id.desc())
        .limit(1)
    )
    if latest_stage is not None and _STAGE_ORDER[details.stage] < _STAGE_ORDER[latest_stage]:
        raise StageRegressionError(latest_stage)

    crop_update = CropUpdate(grow_offer_id=locked_offer.id, **details.model_dump())
    db.add(crop_update)

    became_ready = False
    if details.stage is CropStage.READY and locked_offer.status in (
        GrowOfferStatus.CONFIRMED,
        GrowOfferStatus.GROWING,
    ):
        locked_offer.status = GrowOfferStatus.READY
        became_ready = True
    elif (
        details.stage in _GROWING_STAGES and locked_offer.status is GrowOfferStatus.CONFIRMED
    ):
        locked_offer.status = GrowOfferStatus.GROWING

    if became_ready:
        notify_committed_customers(
            db, locked_offer, NotificationType.CROP_READY, crop_ready_message(locked_offer)
        )
    else:
        notify_committed_customers(
            db,
            locked_offer,
            NotificationType.CROP_UPDATE_POSTED,
            crop_update_message(locked_offer, details.stage),
        )

    db.commit()
    return crop_update
