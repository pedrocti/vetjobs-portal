from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum


from .tokens import PasswordResetToken

from .tokens import PasswordResetToken

from .profile_veteran import VeteranProfile

from .user import User

from .jobpost import JobPosting

from .employer import EmployerProfile

from .jobapplication import JobApplication

from .payment import Payment 

from .subscription import Subscription 

from .partner import Partner, TrainingProgram, TrainingApplication

from .testimonial import Testimonial

from .paymentsetting import PaymentSetting 

from .review import Review

from .emailsetting import EmailSetting

from .services import CVOptimizationRequest 

from .notification import Notification, BroadcastNotification, NotificationPreference



# Search & Matching System Models

class SavedVeteran(db.Model):
    """Employer's saved/favorited veterans for later review."""
    __tablename__ = 'saved_veterans'

    id = db.Column(db.Integer, primary_key=True)
    employer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    veteran_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    notes = db.Column(db.Text)  # Employer's private notes about the veteran
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    employer = db.relationship('User', foreign_keys=[employer_id], backref=db.backref('saved_veterans', lazy='dynamic'))
    veteran = db.relationship('User', foreign_keys=[veteran_id], backref=db.backref('saved_by_employers', lazy='dynamic'))

    # Unique constraint to prevent duplicate saves
    __table_args__ = (
        db.UniqueConstraint('employer_id', 'veteran_id', name='unique_saved_veteran'),
    )

    @classmethod
    def is_saved(cls, employer_id, veteran_id):
        """Check if a veteran is saved by an employer."""
        return cls.query.filter_by(employer_id=employer_id, veteran_id=veteran_id).first() is not None

    def __repr__(self):
        return f'<SavedVeteran employer:{self.employer_id} veteran:{self.veteran_id}>'


class SavedJob(db.Model):
            """Veteran's saved/bookmarked jobs for later application."""
            __tablename__ = 'saved_jobs'

            id = db.Column(db.Integer, primary_key=True)
            veteran_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
            job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False, index=True)  # fixed FK
            notes = db.Column(db.Text)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)

            # Relationships
            veteran = db.relationship('User', backref=db.backref('saved_jobs', lazy='dynamic'))
            job = db.relationship('JobPosting', backref=db.backref('saved_by_veterans', lazy='dynamic'))  # fixed

            __table_args__ = (
                db.UniqueConstraint('veteran_id', 'job_id', name='unique_saved_job'),
            )

            @classmethod
            def is_saved(cls, veteran_id, job_id):
                return cls.query.filter_by(veteran_id=veteran_id, job_id=job_id).first() is not None

            def __repr__(self):
                return f'<SavedJob veteran:{self.veteran_id} job:{self.job_id}>'



class SearchLog(db.Model):
    """Log of all search activities for analytics."""
    __tablename__ = 'search_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)  # Nullable for anonymous searches
    search_type = db.Column(db.String(20), nullable=False, index=True)  # 'veteran', 'job'
    query_terms = db.Column(db.Text)  # Search keywords
    filters_used = db.Column(db.JSON)  # JSON of applied filters
    results_count = db.Column(db.Integer, default=0)
    clicked_result_id = db.Column(db.Integer)  # ID of result clicked (if any)
    session_id = db.Column(db.String(100), index=True)  # Track session for anonymous users
    ip_address = db.Column(db.String(45))  # For analytics
    user_agent = db.Column(db.Text)  # Browser info
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Relationship
    user = db.relationship('User', backref=db.backref('search_logs', lazy='dynamic'))

    @classmethod
    def log_search(cls, search_type, query_terms=None, filters_used=None, results_count=0, 
                   user_id=None, session_id=None, ip_address=None, user_agent=None):
        """Log a search activity."""
        search_log = cls(
            user_id=user_id,
            search_type=search_type,
            query_terms=query_terms,
            filters_used=filters_used or {},
            results_count=results_count,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.session.add(search_log)
        db.session.commit()
        return search_log

    @classmethod
    def get_popular_search_terms(cls, search_type, days=30, limit=10):
        """Get most popular search terms for analytics."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # This would be more complex in a real implementation with proper text parsing
        results = db.session.query(
            cls.query_terms,
            func.count(cls.id).label('search_count')
        ).filter(
            cls.search_type == search_type,
            cls.created_at >= cutoff_date,
            cls.query_terms.isnot(None)
        ).group_by(cls.query_terms).order_by(
            func.count(cls.id).desc()
        ).limit(limit).all()

        return results

    def __repr__(self):
        return f'<SearchLog {self.search_type}:{self.query_terms}>'


class MatchingScore(db.Model):
            """Store calculated matching scores between veterans and jobs for performance."""
            __tablename__ = 'matching_scores'

            id = db.Column(db.Integer, primary_key=True)
            veteran_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
            job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False, index=True)  # fixed FK
            score = db.Column(db.Float, nullable=False, index=True)
            factors = db.Column(db.JSON)
            calculated_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

            # Relationships
            veteran = db.relationship('User', backref=db.backref('job_matches', lazy='dynamic'))
            job = db.relationship('JobPosting', backref=db.backref('veteran_matches', lazy='dynamic'))  # fixed

            __table_args__ = (
                db.UniqueConstraint('veteran_id', 'job_id', name='unique_matching_score'),
            )

            @classmethod
            def calculate_match_score(cls, veteran_profile, job_post):
                """Calculate match score between veteran and job."""
                score = 0.0
                factors = {}

                # Skills matching (40% weight)
                if veteran_profile.skills and job_post.requirements:
                    veteran_skills = set(skill.strip().lower() for skill in veteran_profile.skills.split(','))
                    job_skills = set(skill.strip().lower() for skill in job_post.requirements.split(','))

                    if job_skills:
                        skills_match = len(veteran_skills.intersection(job_skills)) / len(job_skills)
                        score += skills_match * 0.4
                        factors['skills_match'] = skills_match

                # Location matching (20% weight)
                v_loc = getattr(veteran_profile, 'location', None)
                j_loc = getattr(job_post, 'location', None)
                if v_loc and j_loc:
                    location_match = 1.0 if v_loc.lower() in j_loc.lower() else 0.0
                    score += location_match * 0.2
                    factors['location_match'] = location_match


                # Experience matching (25% weight)
                if veteran_profile.years_of_service and hasattr(job_post, "experience_required"):
                    experience_ratio = min(veteran_profile.years_of_service / max(job_post.experience_required, 1), 1.0)
                    score += experience_ratio * 0.25
                    factors['experience_match'] = experience_ratio

                # Verification status (15% weight)
                if veteran_profile.is_verified:
                    score += 0.15
                    factors['verification_bonus'] = 0.15

                return min(score, 1.0), factors

            @classmethod
            def update_score(cls, veteran_id, job_id, recalculate=False):
                """Update or create matching score."""
                existing = cls.query.filter_by(veteran_id=veteran_id, job_id=job_id).first()

                if not recalculate and existing and existing.calculated_at > datetime.utcnow() - timedelta(hours=24):
                    return existing.score

                from models import VeteranProfile, JobPosting  # fixed import
                veteran_profile = VeteranProfile.query.filter_by(user_id=veteran_id).first()
                job_post = JobPosting.query.get(job_id)  # fixed

                if not veteran_profile or not job_post:
                    return 0.0

                score, factors = cls.calculate_match_score(veteran_profile, job_post)

                if existing:
                    existing.score = score
                    existing.factors = factors
                    existing.calculated_at = datetime.utcnow()
                else:
                    existing = cls(
                        veteran_id=veteran_id,
                        job_id=job_id,
                        score=score,
                        factors=factors
                    )
                    db.session.add(existing)

                db.session.commit()
                return score

            def __repr__(self):
                return f'<MatchingScore veteran:{self.veteran_id} job:{self.job_id} score:{self.score:.2f}>'



class SecurityLog(db.Model):
    """Security audit log for tracking important events."""
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(100), nullable=False)  # 'login', 'failed_login', 'password_change', etc.
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    ip_address = db.Column(db.String(45))  # Supports IPv6
    details = db.Column(db.JSON)  # Additional event details
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    user = db.relationship('User', backref=db.backref('security_logs', lazy=True))

    def __repr__(self):
        return f'<SecurityLog {self.event_type}: {self.user_id if self.user_id else "Anonymous"}>'


class Message(db.Model):
    """Admin messaging system for communicating with veterans and employers."""
    id = db.Column(db.Integer, primary_key=True)

    # Sender and recipient
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Message content
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)

    # Message status
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    priority = db.Column(db.String(20), default='normal', nullable=False)  # 'low', 'normal', 'high', 'urgent'

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime)

    # Relationships
    sender = db.relationship('User', foreign_keys=[sender_id], backref=db.backref('sent_messages', lazy='dynamic'))
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref=db.backref('received_messages', lazy='dynamic'))

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

    @property
    def formatted_created_at(self):
        """Format creation time for display"""
        now = datetime.utcnow()
        diff = now - self.created_at

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"

    @property
    def priority_class(self):
        """Get CSS class for priority display"""
        priority_classes = {
            'low': 'text-muted',
            'normal': 'text-dark',
            'high': 'text-warning',
            'urgent': 'text-danger'
        }
        return priority_classes.get(self.priority, 'text-dark')

    @property
    def priority_icon(self):
        """Get icon for priority display"""
        priority_icons = {
            'low': 'fas fa-circle',
            'normal': 'fas fa-circle',
            'high': 'fas fa-exclamation-triangle',
            'urgent': 'fas fa-exclamation-circle'
        }
        return priority_icons.get(self.priority, 'fas fa-circle')

    def __repr__(self):
        return f'<Message {self.id}: {self.subject[:50]}...>'

class PlatformSettings(db.Model):
    """Platform-level editable labels (platform name, role names)."""
    __tablename__ = 'platform_settings'

    id = db.Column(db.Integer, primary_key=True)
    platform_name = db.Column(db.String(120), nullable=False, default="VetWorkConnect")
    veteran_label = db.Column(db.String(50), nullable=False, default="Veteran")
    employer_label = db.Column(db.String(50), nullable=False, default="Employer")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<PlatformSettings {self.platform_name}>"


class Resource(db.Model):
    __tablename__ = "resources"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    link = db.Column(db.String(500))  
    external_link = db.Column(db.String(500)) 
    category = db.Column(db.String(100))  
    image_url = db.Column(db.String(500)) 
    is_published = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Resource {self.title}>"

