from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'PUT_NEW_ID_HERE'
down_revision = '58865802298f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )


def downgrade():
    op.drop_column('users', 'onboarding_completed')