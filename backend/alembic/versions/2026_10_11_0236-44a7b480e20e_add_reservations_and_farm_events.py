"""add reservations and farm events

Revision ID: 44a7b480e20e
Revises: f85ecd722ec8
Create Date: 2026-10-11 02:36:56.896044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '44a7b480e20e'
down_revision: Union[str, Sequence[str], None] = 'f85ecd722ec8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RESERVATION_STATUS_CHECK = "status IN ('PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED')"


def upgrade() -> None:
    op.create_table(
        'product_reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('pickup_date', sa.Date(), nullable=False),
        sa.Column('pickup_time', sa.Time(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(RESERVATION_STATUS_CHECK, name=op.f('ck_product_reservations_status_allowed')),
        sa.CheckConstraint('quantity > 0', name=op.f('ck_product_reservations_quantity_positive')),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_product_reservations_customer_id_users')),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_product_reservations_product_id_products')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_product_reservations')),
    )
    op.create_index(op.f('ix_product_reservations_customer_id'), 'product_reservations', ['customer_id'], unique=False)
    op.create_index(op.f('ix_product_reservations_product_id'), 'product_reservations', ['product_id'], unique=False)

    op.create_table(
        'farm_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('farm_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('event_date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('STRAWBERRY_PICKING', 'APPLE_PICKING', 'PUMPKIN_PICKING', "
            "'VEGETABLE_PICKING', 'FARM_TOUR', 'OTHER')",
            name=op.f('ck_farm_events_event_type_allowed'),
        ),
        sa.CheckConstraint('capacity > 0', name=op.f('ck_farm_events_capacity_positive')),
        sa.CheckConstraint('end_time > start_time', name=op.f('ck_farm_events_ends_after_it_starts')),
        sa.CheckConstraint('price >= 0', name=op.f('ck_farm_events_price_not_negative')),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_farm_events_farm_id_farms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_farm_events')),
    )
    op.create_index(op.f('ix_farm_events_event_date'), 'farm_events', ['event_date'], unique=False)
    op.create_index(op.f('ix_farm_events_farm_id'), 'farm_events', ['farm_id'], unique=False)

    op.create_table(
        'event_reservations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('party_size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(RESERVATION_STATUS_CHECK, name=op.f('ck_event_reservations_status_allowed')),
        sa.CheckConstraint('party_size > 0', name=op.f('ck_event_reservations_party_size_positive')),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_event_reservations_customer_id_users')),
        sa.ForeignKeyConstraint(['event_id'], ['farm_events.id'], name=op.f('fk_event_reservations_event_id_farm_events')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_event_reservations')),
    )
    op.create_index(op.f('ix_event_reservations_customer_id'), 'event_reservations', ['customer_id'], unique=False)
    op.create_index(op.f('ix_event_reservations_event_id'), 'event_reservations', ['event_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_event_reservations_event_id'), table_name='event_reservations')
    op.drop_index(op.f('ix_event_reservations_customer_id'), table_name='event_reservations')
    op.drop_table('event_reservations')
    op.drop_index(op.f('ix_farm_events_farm_id'), table_name='farm_events')
    op.drop_index(op.f('ix_farm_events_event_date'), table_name='farm_events')
    op.drop_table('farm_events')
    op.drop_index(op.f('ix_product_reservations_product_id'), table_name='product_reservations')
    op.drop_index(op.f('ix_product_reservations_customer_id'), table_name='product_reservations')
    op.drop_table('product_reservations')
