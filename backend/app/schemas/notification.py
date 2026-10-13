from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: NotificationType
    message: str
    read: bool
    created_at: datetime


class UnreadNotificationCount(BaseModel):
    unread: int
