from datetime import date

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.orm import Session

from app.models.farm import Farm
from app.models.product import Product
from app.schemas.product import (
    ProductSearchParams,
    ProductSearchResult,
    ProductSearchSort,
    SearchResultFarm,
    SearchResultProduct,
)
from app.services.clock import marketplace_today
from app.services.geo import geography_point, meters_to_miles, miles_to_meters


def is_available_on(day: date) -> ColumnElement[bool]:
    """In stock, and `day` falls inside the availability window. An open end has no limit."""
    return (
        (Product.quantity_available > 0)
        & or_(Product.available_from.is_(None), Product.available_from <= day)
        & or_(Product.available_until.is_(None), Product.available_until >= day)
    )


def search_products(db: Session, params: ProductSearchParams) -> list[ProductSearchResult]:
    """Find active products on farms within a radius of a point.

    Both the radius filter and the distance are evaluated by PostGIS on the
    geography column: ST_DWithin can use the GiST index on farms.location, and
    ST_Distance measures along the Earth's surface in meters. No farm is
    loaded into Python unless it is inside the radius.
    """
    search_point = geography_point(params.latitude, params.longitude)
    distance_meters = func.ST_Distance(Farm.location, search_point)

    statement = (
        select(Product, Farm, distance_meters.label("distance_meters"))
        .join(Farm, Product.farm_id == Farm.id)
        .where(Product.active.is_(True))
        .where(func.ST_DWithin(Farm.location, search_point, miles_to_meters(params.radius_miles)))
    )

    if params.query is not None:
        statement = statement.where(Product.name.icontains(params.query, autoescape=True))
    if params.category is not None:
        statement = statement.where(Product.category == params.category)
    if params.available_only:
        statement = statement.where(is_available_on(marketplace_today()))

    # Distance and id follow the primary key so equal values keep a stable order.
    if params.sort is ProductSearchSort.PRICE:
        statement = statement.order_by(Product.price.asc(), distance_meters.asc(), Product.id)
    elif params.sort is ProductSearchSort.HARVEST_DATE:
        statement = statement.order_by(
            Product.harvest_date.desc().nulls_last(), distance_meters.asc(), Product.id
        )
    else:
        statement = statement.order_by(distance_meters.asc(), Product.id)

    rows = db.execute(statement.limit(params.limit)).all()
    return [
        ProductSearchResult(
            product=SearchResultProduct.model_validate(product),
            farm=SearchResultFarm.model_validate(farm),
            distance_miles=meters_to_miles(row_distance_meters),
            price=product.price,
            quantity_available=product.quantity_available,
            harvest_date=product.harvest_date,
        )
        for product, farm, row_distance_meters in rows
    ]
