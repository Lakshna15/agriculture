from typing import Annotated

from fastapi import Depends, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentFarmer
from app.dependencies.path_params import ResourceId
from app.models.product import Product
from app.services.farms import get_farm_owned_by
from app.services.products import get_product


def get_owned_product(product_id: ResourceId, farmer: CurrentFarmer, db: DatabaseSession) -> Product:
    """Load a product and confirm it belongs to the signed-in farmer's farm."""
    product = get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    farm = get_farm_owned_by(db, farmer)
    if farm is None or product.farm_id != farm.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only manage your own products",
        )
    return product


OwnedProduct = Annotated[Product, Depends(get_owned_product)]
