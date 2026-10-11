from geoalchemy2 import Geography
from sqlalchemy import ColumnElement, cast, func

METERS_PER_MILE = 1609.344


def geography_point(latitude: float, longitude: float) -> ColumnElement:
    """A PostGIS geography point for use in distance queries."""
    # PostGIS points are (x, y), which means longitude comes first.
    point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    return cast(point, Geography(geometry_type="POINT", srid=4326))


def miles_to_meters(miles: float) -> float:
    return miles * METERS_PER_MILE


def meters_to_miles(meters: float) -> float:
    """Distance in miles, rounded to two decimals for display."""
    return round(meters / METERS_PER_MILE, 2)
