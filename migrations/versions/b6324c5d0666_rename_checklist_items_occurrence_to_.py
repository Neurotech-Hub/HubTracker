"""rename checklist_items occurrence to repeats

Revision ID: b6324c5d0666
Revises: 3040958d632d
Create Date: 2026-08-17 04:27:17.834273

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b6324c5d0666'
down_revision = '3040958d632d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('checklist_items', schema=None) as batch_op:
        batch_op.alter_column('occurrence',
                              new_column_name='repeats',
                              existing_type=sa.String(length=10),
                              existing_nullable=False)


def downgrade():
    with op.batch_alter_table('checklist_items', schema=None) as batch_op:
        batch_op.alter_column('repeats',
                              new_column_name='occurrence',
                              existing_type=sa.String(length=10),
                              existing_nullable=False)
