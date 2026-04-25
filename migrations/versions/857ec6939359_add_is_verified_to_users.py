from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '857ec6939359'
down_revision = 'd77ed54bddcc'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_verified column safely
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_verified', sa.Boolean(), nullable=True))


def downgrade():
    # Remove is_verified column
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_verified')