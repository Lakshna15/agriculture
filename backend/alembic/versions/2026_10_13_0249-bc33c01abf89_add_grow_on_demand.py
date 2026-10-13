"""add grow on demand

Revision ID: bc33c01abf89
Revises: 44a7b480e20e
Create Date: 2026-10-13 02:49:51.562838

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bc33c01abf89'
down_revision: Union[str, Sequence[str], None] = '44a7b480e20e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UNIT_CHECK = "unit IN ('LB', 'OZ', 'EACH', 'DOZEN', 'BUNCH', 'PINT', 'QUART', 'GALLON')"


def upgrade() -> None:
    op.create_table(
        'crop_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('crop_name', sa.String(length=80), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('frequency', sa.String(length=20), nullable=False),
        sa.Column('latitude', sa.Double(), nullable=False),
        sa.Column('longitude', sa.Double(), nullable=False),
        sa.Column('radius_miles', sa.Integer(), nullable=False),
        sa.Column('preferred_season', sa.String(length=20), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='OPEN', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("frequency IN ('ONE_TIME', 'WEEKLY', 'MONTHLY')", name=op.f('ck_crop_requests_frequency_allowed')),
        sa.CheckConstraint(
            "preferred_season IN ('SPRING', 'SUMMER', 'FALL', 'WINTER')",
            name=op.f('ck_crop_requests_preferred_season_allowed'),
        ),
        sa.CheckConstraint("status IN ('OPEN', 'CANCELLED')", name=op.f('ck_crop_requests_status_allowed')),
        sa.CheckConstraint(UNIT_CHECK, name=op.f('ck_crop_requests_unit_allowed')),
        sa.CheckConstraint('latitude BETWEEN -90 AND 90', name=op.f('ck_crop_requests_latitude_range')),
        sa.CheckConstraint('longitude BETWEEN -180 AND 180', name=op.f('ck_crop_requests_longitude_range')),
        sa.CheckConstraint('quantity > 0', name=op.f('ck_crop_requests_quantity_positive')),
        sa.CheckConstraint('radius_miles BETWEEN 1 AND 500', name=op.f('ck_crop_requests_radius_range')),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_crop_requests_customer_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crop_requests')),
    )
    # The matching point is the customer's location rounded to two decimal
    # places. PostgreSQL generates it, so it always follows the coordinates.
    op.execute(
        """
        ALTER TABLE crop_requests
        ADD COLUMN approximate_location geography(Point, 4326) NOT NULL
        GENERATED ALWAYS AS (
            ST_SetSRID(
                ST_MakePoint(
                    round(longitude::numeric, 2)::double precision,
                    round(latitude::numeric, 2)::double precision
                ),
                4326
            )::geography
        ) STORED
        """
    )
    op.create_index(
        'ix_crop_requests_approximate_location',
        'crop_requests',
        ['approximate_location'],
        unique=False,
        postgresql_using='gist',
    )
    op.create_index(op.f('ix_crop_requests_crop_name'), 'crop_requests', ['crop_name'], unique=False)
    op.create_index(op.f('ix_crop_requests_customer_id'), 'crop_requests', ['customer_id'], unique=False)
    # At most one open request per customer per crop.
    op.create_index(
        'uq_crop_requests_open_customer_crop',
        'crop_requests',
        ['customer_id', 'crop_name'],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
    )

    op.create_table(
        'grow_offers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('farm_id', sa.Integer(), nullable=False),
        sa.Column('crop_name', sa.String(length=80), nullable=False),
        sa.Column('expected_quantity', sa.Integer(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('estimated_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('planting_date', sa.Date(), nullable=False),
        sa.Column('expected_harvest_date', sa.Date(), nullable=False),
        sa.Column('minimum_customers', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='OPEN', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CONFIRMED', 'GROWING', 'READY', 'COMPLETED', 'CANCELLED')",
            name=op.f('ck_grow_offers_status_allowed'),
        ),
        sa.CheckConstraint(UNIT_CHECK, name=op.f('ck_grow_offers_unit_allowed')),
        sa.CheckConstraint('estimated_price > 0', name=op.f('ck_grow_offers_estimated_price_positive')),
        sa.CheckConstraint('expected_harvest_date >= planting_date', name=op.f('ck_grow_offers_harvest_after_planting')),
        sa.CheckConstraint('expected_quantity > 0', name=op.f('ck_grow_offers_expected_quantity_positive')),
        sa.CheckConstraint('minimum_customers > 0', name=op.f('ck_grow_offers_minimum_customers_positive')),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_grow_offers_farm_id_farms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_grow_offers')),
    )
    op.create_index(op.f('ix_grow_offers_crop_name'), 'grow_offers', ['crop_name'], unique=False)
    op.create_index(op.f('ix_grow_offers_farm_id'), 'grow_offers', ['farm_id'], unique=False)

    op.create_table(
        'crop_commitments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grow_offer_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('quantity > 0', name=op.f('ck_crop_commitments_quantity_positive')),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_crop_commitments_customer_id_users')),
        sa.ForeignKeyConstraint(
            ['grow_offer_id'], ['grow_offers.id'], name=op.f('fk_crop_commitments_grow_offer_id_grow_offers')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crop_commitments')),
        sa.UniqueConstraint('grow_offer_id', 'customer_id', name='uq_crop_commitments_grow_offer_id_customer_id'),
    )
    op.create_index(op.f('ix_crop_commitments_customer_id'), 'crop_commitments', ['customer_id'], unique=False)
    op.create_index(op.f('ix_crop_commitments_grow_offer_id'), 'crop_commitments', ['grow_offer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_crop_commitments_grow_offer_id'), table_name='crop_commitments')
    op.drop_index(op.f('ix_crop_commitments_customer_id'), table_name='crop_commitments')
    op.drop_table('crop_commitments')
    op.drop_index(op.f('ix_grow_offers_farm_id'), table_name='grow_offers')
    op.drop_index(op.f('ix_grow_offers_crop_name'), table_name='grow_offers')
    op.drop_table('grow_offers')
    op.drop_index(
        'uq_crop_requests_open_customer_crop',
        table_name='crop_requests',
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.drop_index(op.f('ix_crop_requests_customer_id'), table_name='crop_requests')
    op.drop_index(op.f('ix_crop_requests_crop_name'), table_name='crop_requests')
    op.drop_index('ix_crop_requests_approximate_location', table_name='crop_requests', postgresql_using='gist')
    op.drop_table('crop_requests')
