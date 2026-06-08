"""Add external_customer_tax to quotes

Revision ID: e5f1a8c9d72b
Revises: d4e8f1a2b3c4
Create Date: 2026-06-08 11:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'e5f1a8c9d72b'
down_revision = 'd4e8f1a2b3c4'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    quote_cols = {c['name'] for c in insp.get_columns('quotes')}
    if 'external_customer_tax' not in quote_cols:
        with op.batch_alter_table('quotes', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('external_customer_tax', sa.Boolean(), nullable=False, server_default='0')
            )


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('external_customer_tax')
