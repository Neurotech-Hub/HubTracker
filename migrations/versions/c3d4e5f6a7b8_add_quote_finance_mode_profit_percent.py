"""Add quote finance_mode and profit_percent for Finances P/L

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-29 05:35:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    quote_cols = {c['name'] for c in insp.get_columns('quotes')}

    with op.batch_alter_table('quotes', schema=None) as batch_op:
        if 'finance_mode' not in quote_cols:
            batch_op.add_column(
                sa.Column('finance_mode', sa.String(length=20), nullable=False, server_default='payback')
            )
        if 'profit_percent' not in quote_cols:
            batch_op.add_column(
                sa.Column('profit_percent', sa.Integer(), nullable=False, server_default='50')
            )


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('profit_percent')
        batch_op.drop_column('finance_mode')
