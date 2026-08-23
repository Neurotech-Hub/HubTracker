"""Add finances snapshot fields: user salary, funding payout, quote paid, finance settings

Revision ID: a1f2e3d4c5b6
Revises: b6324c5d0666
Create Date: 2026-08-23 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'a1f2e3d4c5b6'
down_revision = 'b6324c5d0666'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())

    user_cols = {c['name'] for c in insp.get_columns('users')}
    if 'annual_salary' not in user_cols:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.add_column(sa.Column('annual_salary', sa.Numeric(12, 2), nullable=True))

    funding_cols = {c['name'] for c in insp.get_columns('membership_funding')}
    if 'payout' not in funding_cols:
        with op.batch_alter_table('membership_funding', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('payout', sa.String(length=10), nullable=False, server_default='monthly')
            )

    quote_cols = {c['name'] for c in insp.get_columns('quotes')}
    if 'paid_at' not in quote_cols:
        with op.batch_alter_table('quotes', schema=None) as batch_op:
            batch_op.add_column(sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))

    if 'finance_settings' not in insp.get_table_names():
        op.create_table(
            'finance_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('fy_start_year', sa.Integer(), nullable=False),
            sa.Column('fixed_costs', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    op.drop_table('finance_settings')
    with op.batch_alter_table('quotes', schema=None) as batch_op:
        batch_op.drop_column('paid_at')
    with op.batch_alter_table('membership_funding', schema=None) as batch_op:
        batch_op.drop_column('payout')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('annual_salary')
