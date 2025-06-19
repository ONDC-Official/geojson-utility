"""Drop csv_rows table

Revision ID: 0fce9e1f225f
Revises: f35e1ec66a64
Create Date: 2025-06-19 05:03:25.722833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fce9e1f225f'
down_revision: Union[str, Sequence[str], None] = 'f35e1ec66a64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('csv_rows')



def downgrade() -> None:
    """Downgrade schema."""
    pass
