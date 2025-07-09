"""Add activity logs table

Revision ID: add_activity_logs_table
Revises: 7c795898ad28
Create Date: 2024-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_activity_logs_table'
down_revision = '7c795898ad28'
branch_labels = None
depends_on = None


def upgrade():
    # Check if table already exists (in case it was created by db.create_all())
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('activity_logs'):
        # Create activity_logs table
        op.create_table('activity_logs',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('activity_type', sa.String(length=50), nullable=False),
            sa.Column('entity_type', sa.String(length=50), nullable=False),
            sa.Column('entity_id', sa.Integer(), nullable=False),
            sa.Column('old_value', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('new_value', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('extra_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade():
    op.drop_table('activity_logs') 