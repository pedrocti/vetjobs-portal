from app import db
from datetime import datetime


class JobPosting(db.Model):
    """Job posting model."""
    __tablename__ = "job_postings"

    id = db.Column(db.Integer, primary_key=True)

    # Job details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text, nullable=False)
    benefits = db.Column(db.Text, nullable=True)           # ✅ NEW
    company_name = db.Column(db.String(100), nullable=False)
    company_logo = db.Column(db.String(255))               # uploadable logo path

    location = db.Column(db.String(100), nullable=False)

    # Salary fields
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)

    # Plan-based features
    is_featured = db.Column(db.Boolean, default=False)
    promote_on_social = db.Column(db.Boolean, default=False)

    # Job type
    job_type = db.Column(db.String(50), nullable=False, default="full-time")

    # Extra attributes
    industry = db.Column(db.String(100))
    experience_level = db.Column(db.String(50))
    is_veteran_friendly = db.Column(db.Boolean, default=False)

    # Application details
    deadline = db.Column(db.Date, nullable=True)                        # ✅ NEW
    external_apply_url = db.Column(db.String(500), nullable=True)       # ✅ NEW

    # Employer (User)
    posted_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    # Moderation + status
    status = db.Column(db.String(20), default="pending", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    moderated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employer = db.relationship("User", foreign_keys=[posted_by],
                               backref=db.backref("job_postings", lazy=True))
    moderated_by_admin = db.relationship("User", foreign_keys=[moderated_by])

    # ---- Display / Utility Methods ----

    JOB_TYPE_CHOICES = {
        "full-time": "Full-time",
        "part-time": "Part-time",
        "contract": "Contract",
    }

    STATUS_DISPLAY = {
        "pending": "Pending Review",
        "approved": "Approved",
        "rejected": "Rejected",
        "flagged": "Flagged for Review",
    }

    def get_job_type_display(self):
        return self.JOB_TYPE_CHOICES.get(self.job_type, self.job_type)

    def get_status_display(self):
        return self.STATUS_DISPLAY.get(self.status, self.status.capitalize())

    def get_status_badge_class(self):
        badge_classes = {
            "pending": "warning",
            "approved": "success",
            "rejected": "danger",
            "flagged": "secondary",
        }
        return badge_classes.get(self.status, "secondary")

    def is_expired(self):
        """Returns True if deadline has passed."""
        if self.deadline:
            return datetime.utcnow().date() > self.deadline
        return False

    def days_until_deadline(self):
        """Returns days remaining, or None if no deadline set."""
        if self.deadline:
            delta = self.deadline - datetime.utcnow().date()
            return delta.days
        return None

    def __repr__(self):
        return f"<JobPosting {self.title} at {self.company_name}>"

    # ---- Compatibility Alias ----
    @property
    def job_title(self):
        """Alias for backward compatibility with old code/templates"""
        return self.title

    @job_title.setter
    def job_title(self, value):
        self.title = value

    # ---- Logo helper ----
    def get_company_logo(self):
        """
        Returns the correct logo for display:
        - Job-level logo if uploaded (admin-posted jobs with company logo)
        - Employer profile logo if available
        - Platform fallback logo
        """
        if self.company_logo:
            return self.company_logo
        if self.employer and hasattr(self.employer, 'employer_profile') \
                and self.employer.employer_profile \
                and self.employer.employer_profile.company_logo:
            return 'uploads/' + self.employer.employer_profile.company_logo
        return "images/vetjoblogo1.png"

    # ---- Business Logic ----
    @staticmethod
    def can_be_posted_by(user):
        """
        Check if a user can post a job:
        - Must be an employer OR admin
        - Employers must have an active subscription
        """
        if not user:
            return False

        if getattr(user, "is_admin", False):
            return True

        if user.user_type != "employer":
            return False

        if not getattr(user, "subscription", None):
            return False

        return user.subscription.can_post_job(user.id)
