"""Add admin_edit_unlocked to quotes

Revision ID: d4e8f1a2b3c4
Revises: 9d4a6e1b2c33
Create Date: 2026-05-06 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'd4e8f1a2b3c4'
down_revision = '9d4a6e1b2c33'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    quote_cols = {c['name'] for c in insp.get_columns('quotes')}
    if 'admin_edit_unlocked' not in quote_cols:
        with op.batch_alter_table('quotes', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('admin_edit_unlocked', sa.Boolean(), nullable=False, server_default='0')
            )


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('admin_edit_unlocked')
