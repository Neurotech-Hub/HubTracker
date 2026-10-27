"""Add sites analytics tables

Revision ID: a7c3e9b14d20
Revises: c3d4e5f6a7b8
Create Date: 2026-10-27 05:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7c3e9b14d20'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('slug', sa.String(length=80), nullable=False),
        sa.Column('origin', sa.String(length=255), nullable=False),
        sa.Column('path_prefix', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_sites_slug'), ['slug'], unique=True)

    op.create_table(
        'site_pageviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('referrer_host', sa.String(length=255), nullable=False),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('site_pageviews', schema=None) as batch_op:
        batch_op.create_index('ix_site_pageviews_site_created', ['site_id', 'created_at'], unique=False)

    op.create_table(
        'site_daily',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('views', sa.Integer(), nullable=False),
        sa.Column('sessions', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id', 'day', name='uq_site_daily'),
    )
    op.create_table(
        'site_daily_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('path', sa.String(length=500), nullable=False),
        sa.Column('views', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id', 'day', 'path', name='uq_site_daily_page'),
    )
    op.create_table(
        'site_daily_referrers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('site_id', sa.Integer(), nullable=False),
        sa.Column('day', sa.Date(), nullable=False),
        sa.Column('referrer_host', sa.String(length=255), nullable=False),
        sa.Column('views', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['site_id'], ['sites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('site_id', 'day', 'referrer_host', name='uq_site_daily_referrer'),
    )


def downgrade():
    op.drop_table('site_daily_referrers')
    op.drop_table('site_daily_pages')
    op.drop_table('site_daily')
    with op.batch_alter_table('site_pageviews', schema=None) as batch_op:
        batch_op.drop_index('ix_site_pageviews_site_created')
    op.drop_table('site_pageviews')
    with op.batch_alter_table('sites', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sites_slug'))
    op.drop_table('sites')
