"""Make units multiplier integer

Revision ID: 9d4a6e1b2c33
Revises: 8c1e5d2f4a90
Create Date: 2026-05-01 09:31:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '9d4a6e1b2c33'
down_revision = '8c1e5d2f4a90'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    qc = {c['name']: c for c in insp.get_columns('quotes')}
    col_info = qc.get('units_multiplier')
    if col_info is None:
        return
    # Already migrated (e.g. alembic lagged behind schema created elsewhere)
    if isinstance(col_info['type'], sa.Integer):
        return

    op.execute(
        "UPDATE quotes "
        "SET units_multiplier = GREATEST(1, ROUND(COALESCE(units_multiplier, 1))::int)"
    )
    op.alter_column(
        'quotes',
        'units_multiplier',
        existing_type=sa.Numeric(10, 2),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using='units_multiplier::integer',
    )
    op.alter_column('quotes', 'units_multiplier', server_default='1')


def downgrade():
    op.alter_column(
        'quotes',
        'units_multiplier',
        existing_type=sa.Integer(),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
        postgresql_using='units_multiplier::numeric',
    )
    op.alter_column('quotes', 'units_multiplier', server_default='1')
