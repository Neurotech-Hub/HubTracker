"""Replace is_admin with role column

Revision ID: 3e93f60c384c
Revises: 3dc918762ece
Create Date: 2024-03-26 12:34:56.789012

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e93f60c384c'
down_revision = '3dc918762ece'
branch_labels = None
depends_on = None


def upgrade():
    # Add new role column
    op.add_column('users', sa.Column('role', sa.String(length=20), nullable=False, server_default='trainee'))
    
    # Update existing admin users
    op.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
    op.execute("UPDATE users SET role = 'trainee' WHERE is_admin = 0")
    
    # Remove old is_admin column
    op.drop_column('users', 'is_admin')


def downgrade():
    # Add back is_admin column
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'))
    
    # Update is_admin based on role
    op.execute("UPDATE users SET is_admin = 1 WHERE role = 'admin'")
    op.execute("UPDATE users SET is_admin = 0 WHERE role != 'admin'")
    
    # Remove role column
    op.drop_column('users', 'role')
