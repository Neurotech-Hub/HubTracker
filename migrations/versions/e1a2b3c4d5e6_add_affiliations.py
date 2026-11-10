"""Add affiliations table and client.affiliation_id

Revision ID: e1a2b3c4d5e6
Revises: d8e2f4a1b9c0
Create Date: 2026-11-10 07:40:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'e1a2b3c4d5e6'
down_revision = 'd8e2f4a1b9c0'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    tables = insp.get_table_names()

    if 'affiliations' not in tables:
        op.create_table(
            'affiliations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('is_internal', sa.Boolean(), nullable=False, server_default=sa.text('true')),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )

    if 'clients' in tables:
        client_cols = {c['name'] for c in insp.get_columns('clients')}
        if 'affiliation_id' not in client_cols:
            with op.batch_alter_table('clients', schema=None) as batch_op:
                batch_op.add_column(sa.Column('affiliation_id', sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    'fk_clients_affiliation_id',
                    'affiliations',
                    ['affiliation_id'],
                    ['id'],
                    ondelete='SET NULL',
                )


def downgrade():
    insp = inspect(op.get_bind())
    tables = insp.get_table_names()

    if 'clients' in tables:
        client_cols = {c['name'] for c in insp.get_columns('clients')}
        if 'affiliation_id' in client_cols:
            with op.batch_alter_table('clients', schema=None) as batch_op:
                batch_op.drop_constraint('fk_clients_affiliation_id', type_='foreignkey')
                batch_op.drop_column('affiliation_id')

    if 'affiliations' in tables:
        op.drop_table('affiliations')
