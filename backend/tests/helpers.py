from typing import Any

from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.user import User, UserRole
from app.services.security import create_access_token, hash_password

DEFAULT_PASSWORD = "correct-horse-battery"


def create_user(
    db_session: Session,
    *,
    role: UserRole,
    email: str,
    name: str = "Test User",
    password: str = DEFAULT_PASSWORD,
) -> User:
    user = User(name=name, email=email, password_hash=hash_password(password), role=role)
    db_session.add(user)
    db_session.commit()
    return user


def auth_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def farm_payload(**overrides: Any) -> dict[str, Any]:
    """A valid farm request body. Coordinates are uptown Charlotte, North Carolina."""
    payload = {
        "farm_name": "Green Acres",
        "description": "Family-run vegetable farm.",
        "address": "100 Orchard Road",
        "city": "Charlotte",
        "state": "NC",
        "zip_code": "28202",
        "latitude": 35.2271,
        "longitude": -80.8431,
        "phone": "704-555-0100",
        "pickup_available": True,
        "delivery_available": False,
    }
    return payload | overrides


def create_farm(db_session: Session, owner: User, **overrides: Any) -> Farm:
    farm = Farm(owner_id=owner.id, **farm_payload(**overrides))
    db_session.add(farm)
    db_session.commit()
    return farm
