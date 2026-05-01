"""Add units multiplier to quotes

Revision ID: 8c1e5d2f4a90
Revises: 7b2d4a1c9e77
Create Date: 2026-05-01 09:28:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8c1e5d2f4a90'
down_revision = '7b2d4a1c9e77'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('units_multiplier', sa.Numeric(10, 2), nullable=False, server_default='1'))
    op.execute("UPDATE quotes SET units_multiplier = 1 WHERE units_multiplier IS NULL")


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('units_multiplier')
