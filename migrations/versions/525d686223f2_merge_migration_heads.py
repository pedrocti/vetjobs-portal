"""merge migration heads

Revision ID: 525d686223f2
Revises: a9f3c2e1b8d7, b3d7f1a2c9e4
Create Date: 2026-05-19 05:15:42.041062

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '525d686223f2'
down_revision = ('a9f3c2e1b8d7', 'b3d7f1a2c9e4')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
