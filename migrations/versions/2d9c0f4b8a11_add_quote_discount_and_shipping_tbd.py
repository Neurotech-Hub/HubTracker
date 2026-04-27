"""Add quote discount and shipping TBD

Revision ID: 2d9c0f4b8a11
Revises: f4a1c2d9b7e3
Create Date: 2026-04-27 11:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d9c0f4b8a11'
down_revision = 'f4a1c2d9b7e3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('shipping_tbd', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('discount_percent')
        batch_op.drop_column('shipping_tbd')
