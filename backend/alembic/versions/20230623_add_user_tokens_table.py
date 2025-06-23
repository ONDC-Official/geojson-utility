"""create user_tokens table

Revision ID: 20230623_add_user_tokens_table
Revises: 42875e74554c
Create Date: 2025-06-23

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20230623_add_user_tokens_table'
down_revision = '42875e74554c'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'user_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(), index=True),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )

def downgrade():
    op.drop_table('user_tokens')
 