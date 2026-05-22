"""Add scraped_jobs staging table for AI veteran job pipeline

Revision ID: a9f3c2e1b8d7
Revises: 
Create Date: 2026-05-18

This table is a STAGING area only.
Scraped jobs wait here for admin approval.
Approved jobs become normal JobPosting records.
Rejected jobs stay here marked rejected.
Your existing job_postings table is never touched by the scraper.
"""

from alembic import op
import sqlalchemy as sa

revision = 'a9f3c2e1b8d7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'scraped_jobs',
        sa.Column('id', sa.Integer(), nullable=False),

        # Source tracking
        sa.Column('source_site', sa.String(100), nullable=False),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('external_id', sa.String(255), nullable=True),

        # Job content (raw from scrape)
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('company_name', sa.String(200), nullable=True),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('job_type', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requirements', sa.Text(), nullable=True),
        sa.Column('salary_info', sa.String(200), nullable=True),

        # AI scoring
        sa.Column('ai_score', sa.Integer(), nullable=True),
        sa.Column('ai_category', sa.String(100), nullable=True),
        sa.Column('ai_reasoning', sa.Text(), nullable=True),
        sa.Column('is_remote', sa.Boolean(), default=False),
        sa.Column('is_veteran_relevant', sa.Boolean(), default=False),

        # Admin workflow
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('published_job_id', sa.Integer(), sa.ForeignKey('job_postings.id'), nullable=True),

        # Timestamps
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_scraped_jobs_status', 'scraped_jobs', ['status'])
    op.create_index('ix_scraped_jobs_source', 'scraped_jobs', ['source_site'])
    op.create_index('ix_scraped_jobs_score', 'scraped_jobs', ['ai_score'])
    op.create_index(
        'ix_scraped_jobs_dedup',
        'scraped_jobs',
        ['source_site', 'external_id'],
        unique=True
    )


def downgrade():
    op.drop_table('scraped_jobs')