from fastapi import APIRouter, HTTPException, Response, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentUser
from app.dependencies.path_params import ResourceId
from app.models.notification import Notification
from app.schemas.notification import NotificationRead, UnreadNotificationCount
from app.services.notifications import (
    count_unread_notifications,
    list_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# Every endpoint here works only on the signed-in user's own notifications.
# There is no way to name another user.
@router.get("", response_model=list[NotificationRead])
def list_my_notifications(current_user: CurrentUser, db: DatabaseSession) -> list[Notification]:
    return list_notifications(db, current_user)


@router.get("/unread-count", response_model=UnreadNotificationCount)
def count_my_unread_notifications(
    current_user: CurrentUser, db: DatabaseSession
) -> UnreadNotificationCount:
    return UnreadNotificationCount(unread=count_unread_notifications(db, current_user))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_my_notifications_read(current_user: CurrentUser, db: DatabaseSession) -> Response:
    mark_all_notifications_read(db, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notification_id}/read", response_model=NotificationRead)
def mark_my_notification_read(
    notification_id: ResourceId, current_user: CurrentUser, db: DatabaseSession
) -> Notification:
    notification = mark_notification_read(db, current_user, notification_id)
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    return notification
