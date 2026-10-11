from datetime import date, datetime, time
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from app.models.farm import Farm
from app.models.product import ProductUnit
from app.models.reservation import ProductReservation, ReservationStatus
from app.schemas.common import DatabaseId
from app.schemas.product import MAX_QUANTITY


class ReservationStatusUpdate(BaseModel):
    status: ReservationStatus


class ReservationFarm(BaseModel):
    """What a customer needs to find the farm and get in touch about a reservation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_name: str
    address: str
    city: str
    state: str
    zip_code: str
    phone: str | None

    @classmethod
    def from_farm(cls, farm: Farm) -> Self:
        return cls.model_validate(farm)


class ProductReservationCreate(BaseModel):
    product_id: DatabaseId
    quantity: int = Field(gt=0, le=MAX_QUANTITY)
    pickup_date: date
    pickup_time: time


class ReservedProduct(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    unit: ProductUnit


class ProductReservationRead(BaseModel):
    id: int
    quantity: int
    pickup_date: date
    pickup_time: time
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime
    # The name is all a farmer is shown about the customer.
    customer_name: str
    product: ReservedProduct
    farm: ReservationFarm

    @classmethod
    def from_reservation(cls, reservation: ProductReservation) -> Self:
        return cls(
            id=reservation.id,
            quantity=reservation.quantity,
            pickup_date=reservation.pickup_date,
            pickup_time=reservation.pickup_time,
            status=reservation.status,
            created_at=reservation.created_at,
            updated_at=reservation.updated_at,
            customer_name=reservation.customer.name,
            product=ReservedProduct.model_validate(reservation.product),
            farm=ReservationFarm.from_farm(reservation.product.farm),
        )
