"""add application events

Revision ID: e1a7c4b9d2f3
Revises: 84cbcd5aa219
Create Date: 2026-10-15 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e1a7c4b9d2f3'
down_revision: Union[str, Sequence[str], None] = '84cbcd5aa219'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'application_events',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('farm_id', sa.Integer(), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('SEARCH_PERFORMED', 'NO_SEARCH_RESULT', 'PRODUCT_VIEWED', 'FARM_VIEWED', "
            "'CROP_REQUESTED', 'GROW_OFFER_CREATED', 'CROP_COMMITTED', 'RESERVATION_CREATED', "
            "'INVENTORY_UPDATED', 'FARM_EVENT_BOOKED')",
            name=op.f('ck_application_events_event_type_allowed'),
        ),
        sa.CheckConstraint("jsonb_typeof(metadata) = 'object'", name=op.f('ck_application_events_metadata_is_object')),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_application_events_farm_id_farms'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], name=op.f('fk_application_events_product_id_products'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_application_events_user_id_users'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_application_events')),
    )
    op.create_index('ix_application_events_created_at', 'application_events', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_application_events_created_at', table_name='application_events')
    op.drop_table('application_events')
