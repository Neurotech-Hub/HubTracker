"""Add user notes and quote projected_fy_month for Finances projections

Revision ID: b2c3d4e5f6a7
Revises: a1f2e3d4c5b6
Create Date: 2026-08-24 05:40:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'b2c3d4e5f6a7'
down_revision = 'a1f2e3d4c5b6'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())

    user_cols = {c['name'] for c in insp.get_columns('users')}
    if 'notes' not in user_cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))

    quote_cols = {c['name'] for c in insp.get_columns('quotes')}
    if 'projected_fy_month' not in quote_cols:
        with op.batch_alter_table('quotes', schema=None) as batch_op:
            batch_op.add_column(sa.Column('projected_fy_month', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('projected_fy_month')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('notes')
