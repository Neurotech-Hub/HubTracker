"""Add billing type and quote approval fields

Revision ID: 7b2d4a1c9e77
Revises: 2d9c0f4b8a11
Create Date: 2026-05-01 09:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '7b2d4a1c9e77'
down_revision = '2d9c0f4b8a11'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    quote_cols = {c['name'] for c in insp.get_columns('quotes')}
    to_add = []
    if 'bill_type' not in quote_cols:
        to_add.append(sa.Column('bill_type', sa.String(length=20), nullable=False, server_default='quote'))
    if 'approved_by_name' not in quote_cols:
        to_add.append(sa.Column('approved_by_name', sa.String(length=255), nullable=True))
    if 'approved_cost_center' not in quote_cols:
        to_add.append(sa.Column('approved_cost_center', sa.String(length=120), nullable=True))
    if 'approved_at' not in quote_cols:
        to_add.append(sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    if to_add:
        with op.batch_alter_table('quotes', schema=None) as batch_op:
            for col in to_add:
                batch_op.add_column(col)

    op.execute("UPDATE quotes SET bill_type = 'quote' WHERE bill_type IS NULL")


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('approved_at')
        batch_op.drop_column('approved_cost_center')
        batch_op.drop_column('approved_by_name')
        batch_op.drop_column('bill_type')
