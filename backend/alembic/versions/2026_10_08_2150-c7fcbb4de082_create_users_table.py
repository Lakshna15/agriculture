"""create users table

Revision ID: c7fcbb4de082
Revises: 77db061d9ced
Create Date: 2026-10-08 21:50:52.075800

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7fcbb4de082'
down_revision: Union[str, Sequence[str], None] = '77db061d9ced'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("role IN ('CUSTOMER', 'FARMER', 'ADMIN')", name=op.f('ck_users_role_allowed')),
        sa.CheckConstraint('email = lower(btrim(email))', name=op.f('ck_users_email_normalized')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    )


def downgrade() -> None:
    op.drop_table('users')
