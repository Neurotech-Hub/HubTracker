"""Add billing type and quote approval fields

Revision ID: 7b2d4a1c9e77
Revises: 2d9c0f4b8a11
Create Date: 2026-05-01 09:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b2d4a1c9e77'
down_revision = '2d9c0f4b8a11'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bill_type', sa.String(length=20), nullable=False, server_default='quote'))
        batch_op.add_column(sa.Column('approved_by_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('approved_cost_center', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE quotes SET bill_type = 'quote' WHERE bill_type IS NULL")


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('approved_at')
        batch_op.drop_column('approved_cost_center')
        batch_op.drop_column('approved_by_name')
        batch_op.drop_column('bill_type')
