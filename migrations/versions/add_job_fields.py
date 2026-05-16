"""add moderated_by, moderated_at, admin_notes, benefits, deadline, external_apply_url to job_postings

Revision ID: a1b2c3d4e5f6
Revises: 9d715c043279
Create Date: 2026-04-27 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '9d715c043279'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL: add columns directly — no batch mode needed

    # Moderation fields (used by approve/reject/flag routes)
    op.add_column('job_postings',
        sa.Column('moderated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('job_postings',
        sa.Column('moderated_at', sa.DateTime(), nullable=True))
    op.add_column('job_postings',
        sa.Column('admin_notes', sa.Text(), nullable=True))

    # Content field (shown in job detail template)
    op.add_column('job_postings',
        sa.Column('benefits', sa.Text(), nullable=True))

    # New admin-only fields
    op.add_column('job_postings',
        sa.Column('deadline', sa.Date(), nullable=True))
    op.add_column('job_postings',
        sa.Column('external_apply_url', sa.String(length=500), nullable=True))


def downgrade():
    op.drop_column('job_postings', 'external_apply_url')
    op.drop_column('job_postings', 'deadline')
    op.drop_column('job_postings', 'benefits')
    op.drop_column('job_postings', 'admin_notes')
    op.drop_column('job_postings', 'moderated_at')
    op.drop_column('job_postings', 'moderated_by')
