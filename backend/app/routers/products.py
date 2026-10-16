from typing import Annotated

from fastapi import APIRouter, Query, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.farms import CurrentFarm
from app.dependencies.products import OwnedProduct
from app.models.product import Product
from app.schemas.product import (
    InventoryUpdate,
    ProductCreate,
    ProductRead,
    ProductSearchParams,
    ProductSearchResult,
    ProductUpdate,
)
from app.services.application_events import record_product_search
from app.services.farms import get_farm_owned_by
from app.services.product_search import search_products
from app.services.products import (
    create_product,
    list_products_of_farm,
    update_product,
    update_product_inventory,
)

router = APIRouter(prefix="/products", tags=["products"])


# Browsing the marketplace needs no account, so the search is public.
@router.get("/search", response_model=list[ProductSearchResult])
def search(
    params: Annotated[ProductSearchParams, Query()], db: DatabaseSession
) -> list[ProductSearchResult]:
    results = search_products(db, params)
    record_product_search(db, params, results)
    return results


@router.get("/mine", response_model=list[ProductRead])
def list_my_products(farmer: CurrentFarmer, db: DatabaseSession) -> list[Product]:
    farm = get_farm_owned_by(db, farmer)
    if farm is None:
        return []
    return list_products_of_farm(db, farm)


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_my_product(
    product_details: ProductCreate, farm: CurrentFarm, db: DatabaseSession
) -> Product:
    return create_product(db, farm, product_details)


@router.put("/{product_id}", response_model=ProductRead)
def update_my_product(
    product_details: ProductUpdate, product: OwnedProduct, db: DatabaseSession
) -> Product:
    return update_product(db, product, product_details)


@router.patch("/{product_id}/inventory", response_model=ProductRead)
def update_my_product_inventory(
    inventory: InventoryUpdate, product: OwnedProduct, farmer: CurrentFarmer, db: DatabaseSession
) -> Product:
    return update_product_inventory(db, product, inventory.quantity_available, farmer)
