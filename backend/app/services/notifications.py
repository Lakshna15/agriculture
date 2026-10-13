from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.crop_update import CropStage
from app.models.grow_offer import CropCommitment, GrowOffer
from app.models.notification import Notification, NotificationType
from app.models.user import User

NOTIFICATION_LIST_LIMIT = 50

_STAGE_DESCRIPTIONS = {
    CropStage.PLANNED: "is planned",
    CropStage.PLANTED: "has been planted",
    CropStage.GERMINATED: "has germinated",
    CropStage.GROWING: "is growing",
    CropStage.FLOWERING: "is flowering",
    CropStage.HARVEST_SOON: "will be harvested soon",
    CropStage.READY: "is ready",
}


def confirmed_message(offer: GrowOffer) -> str:
    return (
        f"{offer.crop_name} at {offer.farm.farm_name} is confirmed. "
        "Enough customers committed, so the farm will grow it."
    )


def crop_update_message(offer: GrowOffer, stage: CropStage) -> str:
    return (
        f"{offer.farm.farm_name} posted an update: "
        f"your {offer.crop_name} {_STAGE_DESCRIPTIONS[stage]}."
    )


def crop_ready_message(offer: GrowOffer) -> str:
    return f"Your {offer.crop_name} from {offer.farm.farm_name} is ready."


def cancelled_message(offer: GrowOffer) -> str:
    return f"{offer.farm.farm_name} cancelled the grow offer for {offer.crop_name}."


def notify_committed_customers(
    db: Session, offer: GrowOffer, notification_type: NotificationType, message: str
) -> None:
    """Queue one notification for every customer committed to an offer. Does not commit.

    The caller owns the transaction, so the notifications are saved together
    with the change they announce, or not at all. Commitments added earlier in
    the same transaction must have been flushed to be included.
    """
    customer_ids = db.scalars(
        select(CropCommitment.customer_id).where(CropCommitment.grow_offer_id == offer.id)
    )
    db.add_all(
        Notification(user_id=customer_id, type=notification_type, message=message)
        for customer_id in customer_ids
    )


def list_notifications(db: Session, user: User) -> list[Notification]:
    """A user's most recent notifications, newest first."""
    statement = (
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(NOTIFICATION_LIST_LIMIT)
    )
    return list(db.scalars(statement))


def count_unread_notifications(db: Session, user: User) -> int:
    statement = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read.is_(False))
    )
    return db.scalar(statement) or 0


def mark_notification_read(db: Session, user: User, notification_id: int) -> Notification | None:
    """Mark one of the user's own notifications as read.

    Returns None for a notification that does not exist or belongs to someone
    else, so the two cases look the same to the caller.
    """
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if notification is None:
        return None
    notification.read = True
    db.commit()
    return notification


def mark_all_notifications_read(db: Session, user: User) -> None:
    db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read.is_(False))
        .values(read=True)
    )
    db.commit()
