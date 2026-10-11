from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.config import get_settings


def marketplace_today() -> date:
    """Today's date where the marketplace operates.

    The server runs in UTC, where the date changes several hours before it does
    for farms and customers in the United States. Using the server's date
    would reject "today" as a pickup day every evening.
    """
    return datetime.now(ZoneInfo(get_settings().marketplace_timezone)).date()
