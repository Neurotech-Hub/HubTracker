"""Cascade-delete logs when project is deleted

Revision ID: c8f1a2b3c4d5
Revises: b1c2d3e4f5a6
Create Date: 2026-04-09

"""
from alembic import op


revision = 'c8f1a2b3c4d5'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('logs', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('logs_project_id_fkey'), type_='foreignkey')
        batch_op.create_foreign_key(
            None, 'projects', ['project_id'], ['id'], ondelete='CASCADE'
        )


def downgrade():
    with op.batch_alter_table('logs', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.create_foreign_key(
            batch_op.f('logs_project_id_fkey'),
            'projects',
            ['project_id'],
            ['id'],
            ondelete='SET NULL',
        )
