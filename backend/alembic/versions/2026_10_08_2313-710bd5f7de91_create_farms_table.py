"""create farms table

Revision ID: 710bd5f7de91
Revises: c7fcbb4de082
Create Date: 2026-10-08 23:13:57.593552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '710bd5f7de91'
down_revision: Union[str, Sequence[str], None] = 'c7fcbb4de082'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'farms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('farm_name', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('address', sa.String(length=200), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=2), nullable=False),
        sa.Column('zip_code', sa.String(length=10), nullable=False),
        sa.Column('latitude', sa.Double(), nullable=False),
        sa.Column('longitude', sa.Double(), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('pickup_available', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('delivery_available', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('latitude BETWEEN -90 AND 90', name=op.f('ck_farms_latitude_range')),
        sa.CheckConstraint('longitude BETWEEN -180 AND 180', name=op.f('ck_farms_longitude_range')),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_farms_owner_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_farms')),
        sa.UniqueConstraint('owner_id', name=op.f('uq_farms_owner_id')),
    )


def downgrade() -> None:
    op.drop_table('farms')
