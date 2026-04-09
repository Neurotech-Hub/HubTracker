"""Drop legacy membership fields and supplements table

Revision ID: 9a7b3c2d1e44
Revises: 4f2a6d9b1c10
Create Date: 2026-04-09 10:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a7b3c2d1e44'
down_revision = '4f2a6d9b1c10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.drop_column('status')
        batch_op.drop_column('start_date')
        batch_op.drop_column('is_annual')
        batch_op.drop_column('cost')
        batch_op.drop_column('time')
        batch_op.drop_column('budget')

    op.drop_table('membership_supplements')


def downgrade():
    op.create_table(
        'membership_supplements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('budget', sa.Float(), nullable=True),
        sa.Column('time', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('memberships', schema=None) as batch_op:
        batch_op.add_column(sa.Column('budget', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('time', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cost', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('is_annual', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('start_date', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='Active'))
