"""add job_tips_sent and hiring_tips_sent

Revision ID: e9d9e8040109
Revises: f378e4633bdc
Create Date: 2026-04-22 21:47:20.737070
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e9d9e8040109'
down_revision = 'f378e4633bdc'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('employer_profile', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'hiring_tips_sent',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))

    with op.batch_alter_table('veteran_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'job_tips_sent',
            sa.Boolean(),
            nullable=False,
            server_default='false'
        ))


def downgrade():
    with op.batch_alter_table('veteran_profiles', schema=None) as batch_op:
        batch_op.drop_column('job_tips_sent')

    with op.batch_alter_table('employer_profile', schema=None) as batch_op:
        batch_op.drop_column('hiring_tips_sent')