"""Widen equipment description and manual columns

Revision ID: d8e2f4a1b9c0
Revises: a7c3e9b14d20
Create Date: 2026-11-02 11:10:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'd8e2f4a1b9c0'
down_revision = 'a7c3e9b14d20'
branch_labels = None
depends_on = None


def upgrade():
    insp = inspect(op.get_bind())
    if 'equipment' not in insp.get_table_names():
        return
    with op.batch_alter_table('equipment', schema=None) as batch_op:
        batch_op.alter_column(
            'description',
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'manual',
            existing_type=sa.String(length=255),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade():
    with op.batch_alter_table('equipment', schema=None) as batch_op:
        batch_op.alter_column(
            'manual',
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'description',
            existing_type=sa.Text(),
            type_=sa.String(length=255),
            existing_nullable=True,
        )
