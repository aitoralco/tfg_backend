"""video status data

Revision ID: bfd634c39601
Revises: ad2cff48f3d3
Create Date: 2026-05-27 19:31:11.369406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# import table and column helpers
from sqlalchemy.sql import table, column

# revision identifiers, used by Alembic.
revision: str = 'bfd634c39601'
down_revision: Union[str, Sequence[str], None] = 'ad2cff48f3d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    video_status_table = table('video_status',
            column('id', sa.Integer),
            column('status_name', sa.String)
        )

    # bulk insert los valores
    op.bulk_insert(
        video_status_table,
        [
            {'id': 1, 'status_name': 'unprocessed'},
            {'id': 2, 'status_name': 'processed'},
            {'id': 3, 'status_name': 'processing'},
            {'id': 4, 'status_name': 'error'}
        ]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM video_status WHERE id IN (1, 2, 3, 4)")
