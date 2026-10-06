"""enable postgis extension

Revision ID: 77db061d9ced
Revises: 
Create Date: 2026-10-06 16:53:09.165539

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '77db061d9ced'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The postgis/postgis image already enables the extension in its default
    # database. Declaring it here keeps the schema reproducible on any
    # PostgreSQL server that has PostGIS installed.
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    # Intentionally left in place: the extension may predate this migration,
    # and other extensions (for example postgis_topology) depend on it.
    pass
