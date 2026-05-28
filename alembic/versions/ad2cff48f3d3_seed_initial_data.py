"""seed initial data

Revision ID: ad2cff48f3d3
Revises: 4cfe4e80739b
Create Date: 2026-05-27 19:19:59.855780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# import table and column helpers
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision: str = 'ad2cff48f3d3'
down_revision: Union[str, Sequence[str], None] = '4cfe4e80739b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # tabla(s) a insertar
    roles_table = table('roles',
        column('id', sa.Integer),
        column('name', sa.String)
        )
    
    video_status_table = table('video_status',
        column('id', sa.Integer),
        column('status', sa.String)
        )

    # bulk insert los valores
    op.bulk_insert(
        roles_table,
        [
            {'id': 1, 'name': 'admin'},
            {'id': 2, 'name': 'user'}
        ],
        video_status_table,
        [
            {'id': 1, 'status': 'unprocessed'},
            {'id': 2, 'status': 'processed'},
            {'id': 3, 'status': 'processing'},
            {'id': 4, 'status': 'error'}
        ]
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Como desahcer las inserciones
    op.execute("DELETE FROM roles WHERE id IN (1, 2)")
    op.execute("DELETE FROM video_status WHERE id IN (1, 2, 3, 4)")
