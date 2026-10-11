from datetime import date, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.event import EventReservation, FarmEvent
from app.models.farm import Farm
from app.models.product import Product
from app.models.reservation import ProductReservation, ReservationStatus
from app.models.user import User, UserRole
from app.services.clock import marketplace_today
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


def create_farmer_with_farm(db_session: Session, email: str, **farm_overrides: Any) -> Farm:
    """A farm together with the farmer account that owns it."""
    farmer = create_user(db_session, role=UserRole.FARMER, email=email)
    return create_farm(db_session, farmer, **farm_overrides)


def product_payload(**overrides: Any) -> dict[str, Any]:
    """A valid product request body."""
    payload = {
        "name": "Heirloom Tomatoes",
        "category": "VEGETABLES",
        "description": "Vine-ripened, picked this week.",
        "price": "4.50",
        "unit": "LB",
        "quantity_available": 20,
        "harvest_date": None,
        "available_from": None,
        "available_until": None,
        "organic": True,
        "active": True,
    }
    return payload | overrides


def create_product(db_session: Session, farm: Farm, **overrides: Any) -> Product:
    """Insert a product directly, without going through the API or the history."""
    fields = product_payload(**overrides)
    fields["price"] = Decimal(str(fields["price"]))
    product = Product(farm_id=farm.id, **fields)
    db_session.add(product)
    db_session.commit()
    return product


def days_from_today(days: int) -> date:
    """A date relative to today as the marketplace sees it."""
    return marketplace_today() + timedelta(days=days)


def create_product_reservation(
    db_session: Session,
    customer: User,
    product: Product,
    *,
    quantity: int = 2,
    status: ReservationStatus = ReservationStatus.PENDING,
) -> ProductReservation:
    """Insert a reservation directly. Stock is not deducted, unlike through the API."""
    reservation = ProductReservation(
        customer_id=customer.id,
        product_id=product.id,
        quantity=quantity,
        pickup_date=days_from_today(1),
        pickup_time=time(10, 30),
        status=status,
    )
    db_session.add(reservation)
    db_session.commit()
    return reservation


def event_payload(**overrides: Any) -> dict[str, Any]:
    """A valid farm event request body, one week from today."""
    payload = {
        "title": "Strawberry Picking Morning",
        "description": "Pick your own strawberries straight from the field.",
        "event_type": "STRAWBERRY_PICKING",
        "event_date": days_from_today(7).isoformat(),
        "start_time": "09:00:00",
        "end_time": "12:00:00",
        "price": "12.00",
        "capacity": 20,
    }
    return payload | overrides


def create_event(db_session: Session, farm: Farm, **overrides: Any) -> FarmEvent:
    """Insert a farm event directly, bypassing the API's date check."""
    fields: dict[str, Any] = {
        "title": "Strawberry Picking Morning",
        "description": "Pick your own strawberries straight from the field.",
        "event_type": "STRAWBERRY_PICKING",
        "event_date": days_from_today(7),
        "start_time": time(9, 0),
        "end_time": time(12, 0),
        "price": Decimal("12.00"),
        "capacity": 20,
    } | overrides
    event = FarmEvent(farm_id=farm.id, **fields)
    db_session.add(event)
    db_session.commit()
    return event


def create_event_reservation(
    db_session: Session,
    customer: User,
    event: FarmEvent,
    *,
    party_size: int = 2,
    status: ReservationStatus = ReservationStatus.PENDING,
) -> EventReservation:
    reservation = EventReservation(
        event_id=event.id, customer_id=customer.id, party_size=party_size, status=status
    )
    db_session.add(reservation)
    db_session.commit()
    return reservation
