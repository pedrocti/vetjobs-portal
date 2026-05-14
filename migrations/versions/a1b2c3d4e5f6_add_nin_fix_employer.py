"""add nin to veteran profiles and fix employer benefits

Revision ID: a1b2c3d4e5f6
Revises: f66b00a51772
Create Date: 2026-05-13

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'e9d9e8040109'
branch_labels = None
depends_on = None

def upgrade():
    # Add NIN to veteran_profiles
    op.add_column('veteran_profiles',
        sa.Column('nin', sa.String(20), nullable=True)
    )
    # Add missing employer fields that exist in model but weren't in earlier migrations
    with op.batch_alter_table('employer_profile') as batch_op:
        try:
            batch_op.add_column(sa.Column('benefits', sa.Text(), nullable=True))
        except Exception:
            pass  # column may already exist

def downgrade():
    op.drop_column('veteran_profiles', 'nin')
