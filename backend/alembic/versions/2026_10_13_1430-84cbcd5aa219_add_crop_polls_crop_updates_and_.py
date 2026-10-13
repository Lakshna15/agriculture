"""add crop polls crop updates and notifications

Revision ID: 84cbcd5aa219
Revises: bc33c01abf89
Create Date: 2026-10-13 14:30:36.020246

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '84cbcd5aa219'
down_revision: Union[str, Sequence[str], None] = 'bc33c01abf89'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'crop_polls',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('farm_id', sa.Integer(), nullable=False),
        sa.Column('question', sa.String(length=200), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='OPEN', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name=op.f('ck_crop_polls_status_allowed')),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], name=op.f('fk_crop_polls_farm_id_farms')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crop_polls')),
    )
    op.create_index(op.f('ix_crop_polls_farm_id'), 'crop_polls', ['farm_id'], unique=False)

    op.create_table(
        'crop_poll_options',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('poll_id', sa.Integer(), nullable=False),
        sa.Column('crop_name', sa.String(length=80), nullable=False),
        sa.ForeignKeyConstraint(['poll_id'], ['crop_polls.id'], name=op.f('fk_crop_poll_options_poll_id_crop_polls')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crop_poll_options')),
        sa.UniqueConstraint('poll_id', 'crop_name', name='uq_crop_poll_options_poll_id_crop_name'),
        # Target of the composite foreign key from crop_votes.
        sa.UniqueConstraint('poll_id', 'id', name='uq_crop_poll_options_poll_id_id'),
    )
    op.create_index(op.f('ix_crop_poll_options_poll_id'), 'crop_poll_options', ['poll_id'], unique=False)

    op.create_table(
        'crop_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('poll_id', sa.Integer(), nullable=False),
        sa.Column('option_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['users.id'], name=op.f('fk_crop_votes_customer_id_users')),
        # A vote's option must belong to the same poll as the vote.
        sa.ForeignKeyConstraint(
            ['poll_id', 'option_id'],
            ['crop_poll_options.poll_id', 'crop_poll_options.id'],
            name='fk_crop_votes_poll_id_option_id_crop_poll_options',
        ),
        sa.ForeignKeyConstraint(['poll_id'], ['crop_polls.id'], name=op.f('fk_crop_votes_poll_id_crop_polls')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crop_votes')),
        # One vote per customer per poll.
        sa.UniqueConstraint('poll_id', 'customer_id', name='uq_crop_votes_poll_id_customer_id'),
    )
    op.create_index(op.f('ix_crop_votes_customer_id'), 'crop_votes', ['customer_id'], unique=False)
    op.create_index(op.f('ix_crop_votes_poll_id'), 'crop_votes', ['poll_id'], unique=False)

    op.create_table(
        'crop_updates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('grow_offer_id', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "stage IN ('PLANNED', 'PLANTED', 'GERMINATED', 'GROWING', 'FLOWERING', 'HARVEST_SOON', 'READY')",
            name=op.f('ck_crop_updates_stage_allowed'),
        ),
        sa.ForeignKeyConstraint(
            ['grow_offer_id'], ['grow_offers.id'], name=op.f('fk_crop_updates_grow_offer_id_grow_offers')
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_crop_updates')),
    )
    op.create_index(op.f('ix_crop_updates_grow_offer_id'), 'crop_updates', ['grow_offer_id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('message', sa.String(length=500), nullable=False),
        sa.Column('read', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "type IN ('GROW_OFFER_CONFIRMED', 'CROP_UPDATE_POSTED', 'CROP_READY', 'GROW_OFFER_CANCELLED')",
            name=op.f('ck_notifications_type_allowed'),
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications')),
    )
    op.create_index(
        'ix_notifications_user_id_created_at', 'notifications', ['user_id', 'created_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_notifications_user_id_created_at', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_crop_updates_grow_offer_id'), table_name='crop_updates')
    op.drop_table('crop_updates')
    op.drop_index(op.f('ix_crop_votes_poll_id'), table_name='crop_votes')
    op.drop_index(op.f('ix_crop_votes_customer_id'), table_name='crop_votes')
    op.drop_table('crop_votes')
    op.drop_index(op.f('ix_crop_poll_options_poll_id'), table_name='crop_poll_options')
    op.drop_table('crop_poll_options')
    op.drop_index(op.f('ix_crop_polls_farm_id'), table_name='crop_polls')
    op.drop_table('crop_polls')
