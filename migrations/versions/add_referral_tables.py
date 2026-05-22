"""Add referral_links and referral_conversions tables

Revision ID: b3d7f1a2c9e4
Revises: (set this to your current head revision)
Create Date: 2026-05-19
"""

from alembic import op
import sqlalchemy as sa

revision = 'b3d7f1a2c9e4'
down_revision = None   # ← IMPORTANT: set this to your current latest migration head
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'referral_links',
        sa.Column('id',          sa.Integer(),     nullable=False),
        sa.Column('code',        sa.String(20),    nullable=False),
        sa.Column('campaign',    sa.String(150),   nullable=False),
        sa.Column('description', sa.Text(),        nullable=True),
        sa.Column('created_by',  sa.Integer(),     nullable=False),
        sa.Column('is_active',   sa.Boolean(),     nullable=False, server_default='true'),
        sa.Column('expires_at',  sa.DateTime(),    nullable=True),
        sa.Column('created_at',  sa.DateTime(),    nullable=False),
        sa.Column('updated_at',  sa.DateTime(),    nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_referral_links_code'),
    )
    op.create_index('ix_referral_links_code', 'referral_links', ['code'])

    op.create_table(
        'referral_conversions',
        sa.Column('id',            sa.Integer(),  nullable=False),
        sa.Column('link_id',       sa.Integer(),  nullable=False),
        sa.Column('user_id',       sa.Integer(),  nullable=False),
        sa.Column('user_type',     sa.String(20), nullable=False),
        sa.Column('is_spouse',     sa.Boolean(),  nullable=False, server_default='false'),
        sa.Column('registered_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['link_id'], ['referral_links.id']),
        sa.ForeignKeyConstraint(['user_id'],  ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_referral_conversions_user'),
    )
    op.create_index('ix_referral_conversions_link', 'referral_conversions', ['link_id'])


def downgrade():
    op.drop_table('referral_conversions')
    op.drop_table('referral_links')