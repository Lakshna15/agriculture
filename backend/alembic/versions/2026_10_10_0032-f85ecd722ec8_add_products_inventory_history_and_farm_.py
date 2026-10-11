"""add products inventory history and farm location

Revision ID: f85ecd722ec8
Revises: 710bd5f7de91
Create Date: 2026-10-10 00:32:52.098469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f85ecd722ec8'
down_revision: Union[str, Sequence[str], None] = '710bd5f7de91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A stored generated column: PostgreSQL fills it for existing farms and
    # keeps it equal to latitude/longitude on every later write.
    op.execute(
        """
        ALTER TABLE farms
        ADD COLUMN location geography(Point, 4326) NOT NULL
        GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED
        """
    )
    op.create_index('ix_farms_location', 'farms', ['location'], unique=False, postgresql_using='gist')

    op.create_table(
        'products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('farm_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('quantity_available', sa.Integer(), server_default='0', nullable=False),
        sa.Column('harvest_date', sa.Date(), nullable=True),
        sa.Column('available_from', sa.Date(), nullable=True),
        sa.Column('available_until', sa.Date(), nullable=True),
        sa.Column('organic', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "category IN ('VEGETABLES', 'FRUITS', 'EGGS', 'DAIRY', 'MEAT', 'HERBS', 'SEASONAL', 'OTHER')",
            name=op.f('ck_products_category_allowed'),
        ),
        sa.CheckConstraint(
            "unit IN ('LB', 'OZ', 'EACH', 'DOZEN', 'BUNCH', 'PINT', 'QUART', 'GALLON')",
            name=op.f('ck_products_unit_allowed'),
        ),
        sa.CheckConstraint(
            'available_until IS NULL OR available_from IS NULL OR available_until >= available_from',
            name=op.f('ck_products_availability_window_ordered'),
        ),
        sa.CheckConstraint('price > 0', name=op.f('ck_products_price_positive')),
        sa.CheckConstraint('quantity_available >= 0', name=op.f('ck_products_quantity_not_negative')),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_products_farm_id_farms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_products')),
    )
    op.create_index(op.f('ix_products_farm_id'), 'products', ['farm_id'], unique=False)

    op.create_table(
        'inventory_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('previous_quantity', sa.Integer(), nullable=False),
        sa.Column('new_quantity', sa.Integer(), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('previous_quantity <> new_quantity', name=op.f('ck_inventory_history_quantity_changed')),
        sa.CheckConstraint(
            'previous_quantity >= 0 AND new_quantity >= 0',
            name=op.f('ck_inventory_history_quantities_not_negative'),
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.id'], name=op.f('fk_inventory_history_product_id_products')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_inventory_history')),
    )
    op.create_index(op.f('ix_inventory_history_product_id'), 'inventory_history', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_inventory_history_product_id'), table_name='inventory_history')
    op.drop_table('inventory_history')
    op.drop_index(op.f('ix_products_farm_id'), table_name='products')
    op.drop_table('products')
    op.drop_index('ix_farms_location', table_name='farms', postgresql_using='gist')
    op.drop_column('farms', 'location')
