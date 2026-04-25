"""Add onboarding_completed to veteran_profile

Revision ID: 7552e0c46f94
Revises: PUT_NEW_ID_HERE
Create Date: 2026-03-02 08:17:31.365747
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7552e0c46f94'
down_revision = 'PUT_NEW_ID_HERE'
branch_labels = None
depends_on = None


def upgrade():
    """
    Safe migration:
    Only adds onboarding_completed column to veteran_profile.
    Does NOT drop or modify any other tables.
    """
    with op.batch_alter_table('veteran_profile', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('onboarding_completed', sa.Boolean(), nullable=True)
        )


def downgrade():
    """
    Safe rollback:
    Only removes onboarding_completed column from veteran_profile.
    """
    with op.batch_alter_table('veteran_profile', schema=None) as batch_op:
        batch_op.drop_column('onboarding_completed')