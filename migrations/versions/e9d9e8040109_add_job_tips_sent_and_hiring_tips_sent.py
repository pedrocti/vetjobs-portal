"""add job_tips_sent and hiring_tips_sent

Revision ID: e9d9e8040109
Revises: f378e4633bdc
Create Date: 2026-04-22 21:47:20.737070
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = 'e9d9e8040109'
down_revision = 'f378e4633bdc'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    columns_employer = [c['name'] for c in inspector.get_columns('employer_profile')]
    columns_veteran = [c['name'] for c in inspector.get_columns('veteran_profiles')]

    # ---- employer_profile ----
    if 'hiring_tips_sent' not in columns_employer:
        with op.batch_alter_table('employer_profile', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'hiring_tips_sent',
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('false')
                )
            )

    # ---- veteran_profiles ----
    if 'job_tips_sent' not in columns_veteran:
        with op.batch_alter_table('veteran_profiles', schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    'job_tips_sent',
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text('false')
                )
            )


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    columns_employer = [c['name'] for c in inspector.get_columns('employer_profile')]
    columns_veteran = [c['name'] for c in inspector.get_columns('veteran_profiles')]

    if 'job_tips_sent' in columns_veteran:
        with op.batch_alter_table('veteran_profiles', schema=None) as batch_op:
            batch_op.drop_column('job_tips_sent')

    if 'hiring_tips_sent' in columns_employer:
        with op.batch_alter_table('employer_profile', schema=None) as batch_op:
            batch_op.drop_column('hiring_tips_sent')
