"""Create membership supplements table

Revision ID: c30eaa358a6d
Revises: 90669c297085
Create Date: 2025-07-02 09:09:27.185805

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision = 'c30eaa358a6d'
down_revision = '90669c297085'
branch_labels = None
depends_on = None


def upgrade():
    # Create membership_supplements table
    op.create_table('membership_supplements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('budget', sa.Float(), nullable=True),
        sa.Column('time', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    # Drop membership_supplements table
    op.drop_table('membership_supplements')
