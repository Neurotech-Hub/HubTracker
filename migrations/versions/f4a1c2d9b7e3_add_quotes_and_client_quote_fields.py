"""Add quotes and client quote fields

Revision ID: f4a1c2d9b7e3
Revises: c8f1a2b3c4d5
Create Date: 2026-04-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4a1c2d9b7e3'
down_revision = 'c8f1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('contact_email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('contact_phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('bill_to_org', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('bill_to_address1', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('bill_to_address2', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('bill_to_city', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('bill_to_state', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('bill_to_postal_code', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('bill_to_country', sa.String(length=120), nullable=True))

    op.create_table(
        'quotes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.String(length=16), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('prepared_by_user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('scope_summary', sa.Text(), nullable=True),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('valid_until', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('shipping_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('terms', sa.Text(), nullable=True),
        sa.Column('public_token', sa.String(length=64), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['prepared_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('quote_id'),
        sa.UniqueConstraint('public_token'),
    )
    op.create_index(op.f('ix_quotes_quote_id'), 'quotes', ['quote_id'], unique=True)
    op.create_index(op.f('ix_quotes_public_token'), 'quotes', ['public_token'], unique=True)

    op.create_table(
        'quote_line_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('item_name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1'),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('line_total', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('line_total >= 0', name='ck_quote_line_items_line_total_non_negative'),
        sa.CheckConstraint('quantity >= 0', name='ck_quote_line_items_quantity_non_negative'),
        sa.CheckConstraint('unit_price >= 0', name='ck_quote_line_items_unit_price_non_negative'),
        sa.ForeignKeyConstraint(['quote_id'], ['quotes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_line_items_quote_id'), 'quote_line_items', ['quote_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_quote_line_items_quote_id'), table_name='quote_line_items')
    op.drop_table('quote_line_items')

    op.drop_index(op.f('ix_quotes_public_token'), table_name='quotes')
    op.drop_index(op.f('ix_quotes_quote_id'), table_name='quotes')
    op.drop_table('quotes')

    with op.batch_alter_table('clients', schema=None) as batch_op:
        batch_op.drop_column('bill_to_country')
        batch_op.drop_column('bill_to_postal_code')
        batch_op.drop_column('bill_to_state')
        batch_op.drop_column('bill_to_city')
        batch_op.drop_column('bill_to_address2')
        batch_op.drop_column('bill_to_address1')
        batch_op.drop_column('bill_to_org')
        batch_op.drop_column('contact_phone')
        batch_op.drop_column('contact_email')
        batch_op.drop_column('contact_name')
