"""
models/scraped_job.py
---------------------
Staging table for AI-discovered jobs.
These live here until you approve or reject them.
Approving creates a real JobPosting — your existing table is never modified by the scraper.
"""

from extensions import db
from datetime import datetime


class ScrapedJob(db.Model):
    __tablename__ = 'scraped_jobs'

    id = db.Column(db.Integer, primary_key=True)

    # ── Source tracking ──────────────────────────────────────
    source_site   = db.Column(db.String(100), nullable=False)
    source_url    = db.Column(db.String(500), nullable=True)
    external_id   = db.Column(db.String(255), nullable=True)

    # ── Job content (raw from scrape) ────────────────────────
    title         = db.Column(db.String(200), nullable=False)
    company_name  = db.Column(db.String(200), nullable=True)
    location      = db.Column(db.String(200), nullable=True)
    job_type      = db.Column(db.String(50),  nullable=True, default='full-time')
    description   = db.Column(db.Text,        nullable=True)
    requirements  = db.Column(db.Text,        nullable=True)
    salary_info   = db.Column(db.String(200), nullable=True)

    # ── AI scoring ───────────────────────────────────────────
    ai_score           = db.Column(db.Integer, nullable=True)   # 0–100
    ai_category        = db.Column(db.String(100), nullable=True)
    ai_reasoning       = db.Column(db.Text, nullable=True)
    is_remote          = db.Column(db.Boolean, default=False)
    is_veteran_relevant = db.Column(db.Boolean, default=False)

    # ── Admin workflow ───────────────────────────────────────
    # status: 'pending' | 'approved' | 'rejected'
    status             = db.Column(db.String(30), nullable=False, default='pending', index=True)
    reviewed_by        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at        = db.Column(db.DateTime, nullable=True)
    published_job_id   = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=True)

    # ── Timestamps ───────────────────────────────────────────
    scraped_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    created_at  = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # ── Relationships ────────────────────────────────────────
    reviewer     = db.relationship('User', foreign_keys=[reviewed_by])
    published_job = db.relationship('JobPosting', foreign_keys=[published_job_id])

    # ── Deduplication index ──────────────────────────────────
    __table_args__ = (
        db.UniqueConstraint('source_site', 'external_id', name='ix_scraped_jobs_dedup'),
    )

    # ── Helpers ──────────────────────────────────────────────
    @property
    def score_color(self):
        if self.ai_score is None:
            return 'secondary'
        if self.ai_score >= 80:
            return 'success'
        if self.ai_score >= 60:
            return 'warning'
        return 'danger'

    @property
    def category_display(self):
        return self.ai_category or 'Uncategorised'

    @property
    def status_badge(self):
        return {
            'pending':  'warning',
            'approved': 'success',
            'rejected': 'danger',
        }.get(self.status, 'secondary')

    def __repr__(self):
        return f'<ScrapedJob {self.title!r} from {self.source_site} [{self.status}]>'