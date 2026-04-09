"""Add membership funding table and backfill legacy data

Revision ID: 4f2a6d9b1c10
Revises: 0b36e8ae4f91
Create Date: 2026-04-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timedelta


# revision identifiers, used by Alembic.
revision = '4f2a6d9b1c10'
down_revision = '0b36e8ae4f91'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'membership_funding',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('membership_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False, server_default='0'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('scope', sa.Text(), nullable=True),
        sa.Column('time_budget', sa.Integer(), nullable=True),
        sa.Column('dollar_budget', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['membership_id'], ['memberships.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    bind = op.get_bind()
    memberships = sa.table(
        'memberships',
        sa.column('id', sa.Integer),
        sa.column('start_date', sa.DateTime(timezone=True)),
        sa.column('cost', sa.Float),
        sa.column('time', sa.Integer),
        sa.column('budget', sa.Float),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    supplements = sa.table(
        'membership_supplements',
        sa.column('id', sa.Integer),
        sa.column('membership_id', sa.Integer),
        sa.column('budget', sa.Float),
        sa.column('time', sa.Integer),
        sa.column('notes', sa.Text),
        sa.column('created_at', sa.DateTime(timezone=True)),
    )
    funding = sa.table(
        'membership_funding',
        sa.column('membership_id', sa.Integer),
        sa.column('amount', sa.Float),
        sa.column('start_date', sa.DateTime(timezone=True)),
        sa.column('end_date', sa.DateTime(timezone=True)),
        sa.column('scope', sa.Text),
        sa.column('time_budget', sa.Integer),
        sa.column('dollar_budget', sa.Float),
        sa.column('notes', sa.Text),
        sa.column('created_at', sa.DateTime(timezone=True)),
        sa.column('updated_at', sa.DateTime(timezone=True)),
    )

    now = datetime.utcnow()
    membership_rows = bind.execute(sa.select(
        memberships.c.id,
        memberships.c.start_date,
        memberships.c.cost,
        memberships.c.time,
        memberships.c.budget,
        memberships.c.created_at,
    )).fetchall()

    for row in membership_rows:
        start_date = row.start_date or row.created_at or now
        end_date = start_date + timedelta(days=365)
        amount = float(row.cost or 0)
        scope = "### Migrated Base Membership Funding\n\nThis funding entry was created from legacy membership-level fields."
        created_at = row.created_at or now
        bind.execute(
            funding.insert().values(
                membership_id=row.id,
                amount=amount,
                start_date=start_date,
                end_date=end_date,
                scope=scope,
                time_budget=row.time,
                dollar_budget=row.budget,
                notes=None,
                created_at=created_at,
                updated_at=created_at,
            )
        )

    supplement_rows = bind.execute(sa.select(
        supplements.c.id,
        supplements.c.membership_id,
        supplements.c.budget,
        supplements.c.time,
        supplements.c.notes,
        supplements.c.created_at,
    )).fetchall()

    for row in supplement_rows:
        start_date = row.created_at or now
        end_date = start_date + timedelta(days=365)
        amount = float(row.budget or 0)
        scope = row.notes or ""
        created_at = row.created_at or now
        bind.execute(
            funding.insert().values(
                membership_id=row.membership_id,
                amount=amount,
                start_date=start_date,
                end_date=end_date,
                scope=scope,
                time_budget=row.time,
                dollar_budget=row.budget,
                notes="Migrated from legacy supplement entry.",
                created_at=created_at,
                updated_at=created_at,
            )
        )


def downgrade():
    op.drop_table('membership_funding')
