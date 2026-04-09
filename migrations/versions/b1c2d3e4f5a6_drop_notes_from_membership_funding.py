"""Drop notes column from membership funding

Revision ID: b1c2d3e4f5a6
Revises: 9a7b3c2d1e44
Create Date: 2026-04-09 11:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = '9a7b3c2d1e44'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('membership_funding', schema=None) as batch_op:
        batch_op.drop_column('notes')


def downgrade():
    with op.batch_alter_table('membership_funding', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sa.Text(), nullable=True))
