from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application_event import ApplicationEventType
from app.models.farm import Farm
from app.models.product import InventoryHistory, Product
from app.models.user import User
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.application_events import record_event


def get_product(db: Session, product_id: int) -> Product | None:
    return db.get(Product, product_id)


def lock_product(db: Session, product_id: int) -> Product | None:
    """Load a product and hold a row lock on it until the transaction ends.

    populate_existing makes the session take the locked row's current values
    even if it already holds the product, so stock is never read from a copy
    loaded before the lock was granted.
    """
    statement = (
        select(Product)
        .where(Product.id == product_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return db.scalar(statement)


def list_products_of_farm(db: Session, farm: Farm) -> list[Product]:
    """Every product of a farm, including inactive ones, most recently created first."""
    statement = (
        select(Product).where(Product.farm_id == farm.id).order_by(Product.id.desc())
    )
    return list(db.scalars(statement))


def change_product_quantity(db: Session, product: Product, new_quantity: int) -> None:
    """Set a product's stock and record the change. Does not commit.

    This is the only place quantity_available is written, which is what
    guarantees that every inventory change has a history row. The caller owns
    the transaction, so the stock and its history are saved or discarded together.
    """
    if product.quantity_available == new_quantity:
        return
    db.add(
        InventoryHistory(
            product_id=product.id,
            previous_quantity=product.quantity_available,
            new_quantity=new_quantity,
        )
    )
    product.quantity_available = new_quantity


def create_product(db: Session, farm: Farm, product_details: ProductCreate) -> Product:
    # ProductCreate has no farm_id, so the farm always comes from the session.
    # Stock starts at zero and is then raised through change_product_quantity,
    # which makes the opening stock the first entry in the product's history.
    product = Product(
        farm_id=farm.id,
        quantity_available=0,
        **product_details.model_dump(exclude={"quantity_available"}),
    )
    db.add(product)
    db.flush()
    change_product_quantity(db, product, product_details.quantity_available)
    db.commit()
    return product


def update_product(db: Session, product: Product, product_details: ProductUpdate) -> Product:
    for field_name, value in product_details.model_dump().items():
        setattr(product, field_name, value)
    db.commit()
    db.refresh(product)
    return product


def update_product_inventory(
    db: Session, product: Product, new_quantity: int, farmer: User
) -> Product:
    # Re-read the row under a lock so that two simultaneous updates each record
    # the quantity that was really there before them.
    lock_product(db, product.id)
    previous_quantity = product.quantity_available
    if new_quantity != previous_quantity:
        change_product_quantity(db, product, new_quantity)
        record_event(
            db,
            ApplicationEventType.INVENTORY_UPDATED,
            user_id=farmer.id,
            farm_id=product.farm_id,
            product_id=product.id,
            metadata={"previous_quantity": previous_quantity, "new_quantity": new_quantity},
        )
    db.commit()
    db.refresh(product)
    return product
