from app import db
from flask_login import UserMixin, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from typing import Optional


class VeteranProfile(db.Model):
    """Veteran & Military Spouse profile model for verification and detailed information."""
    __tablename__ = "veteran_profiles"

    # ==========================
    # Service Branch Choices
    # ==========================

    SERVICE_BRANCHES = {  # NEW
        "army": "Army",
        "navy": "Navy",
        "airforce": "Air Force",
        "marines": "Marines",
        "coast_guard": "Coast Guard",
        "space_force": "Space Force",
        "national_guard": "National Guard",
        "reserves": "Reserves",
        "other": "Other"
    }

    # ==========================
    # Columns
    # ==========================

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

    # Core Military Information
    service_branch = db.Column(db.String(50), nullable=False)
    service_number = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    years_of_service = db.Column(db.Integer, nullable=False)
    age = db.Column(db.Integer, nullable=False)
    rank = db.Column(db.String(100))

    # Military Spouse Support
    is_military_spouse = db.Column(db.Boolean, default=False, nullable=False)
    spouse_service_branch = db.Column(db.String(50), nullable=True)
    spouse_rank = db.Column(db.String(100), nullable=True)
    spouse_years_of_service = db.Column(db.Integer, nullable=True)
    relocation_ready = db.Column(db.Boolean, default=False, nullable=False)
    employment_gap_explanation = db.Column(db.Text, nullable=True)

    # Documents
    discharge_document = db.Column(db.String(255))
    id_document = db.Column(db.String(255))
    resume_file = db.Column(db.String(255), nullable=True)
    resume_last_updated = db.Column(db.DateTime, nullable=True)

    # Profile Information
    location = db.Column(db.String(100))
    bio = db.Column(db.Text)
    skills = db.Column(db.Text)
    certifications = db.Column(db.Text)
    discharge_type = db.Column(db.String(50))
    deployment_history = db.Column(db.Text)

    # Verification
    is_verified = db.Column(db.Boolean, default=False)
    verification_status = db.Column(db.String(50), default='pending')
    admin_notes = db.Column(db.Text)
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    verified_at = db.Column(db.DateTime)

    # Boost Feature
    profile_boosted_until = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Tips
    job_tips_sent = db.Column(db.Boolean, default=False, nullable=False)


    # ==========================
    # Relationships
    # ==========================

    user = db.relationship(
        'User',
        foreign_keys=[user_id],
        backref=db.backref('veteran_profile', uselist=False)
    )

    verified_by_admin = db.relationship(
        "User",
        foreign_keys=[verified_by],
        backref=db.backref("verified_veteran_profiles", lazy="dynamic")
    )

    # ==========================
    # Constructor
    # ==========================

    def __init__(
        self,
        user_id: int,
        service_branch: str = "",
        service_number: str = "",
        department: str = "",
        years_of_service: int = 0,
        age: int = 0,
        discharge_document: Optional[str] = None,
        id_document: Optional[str] = None,
        resume_file: Optional[str] = None
    ):
        self.user_id = user_id
        self.service_branch = service_branch
        self.service_number = service_number
        self.department = department
        self.years_of_service = years_of_service
        self.age = age
        self.discharge_document = discharge_document
        self.id_document = id_document
        self.resume_file = resume_file

    # ==========================
    # Utility & Helper Functions
    # ==========================

    def profile_completion_percentage(self) -> int:
        """Accurate and clean profile completion calculation."""

        def is_filled(value):
            if value is None:
                return False
            if isinstance(value, str):
                return value.strip() != ""
            return True

        fields = [
            self.service_branch,
            self.service_number,
            self.department,
            self.years_of_service,
            self.age,
            self.rank,  # ✅ now included
            self.bio,
            self.location,
            self.skills,
            self.certifications,
            self.discharge_type,
            self.discharge_document,
            self.id_document,
            self.resume_file,
        ]

        completed = sum(1 for f in fields if is_filled(f))
        total = len(fields)

        # Spouse logic
        if self.is_military_spouse:
            spouse_fields = [
                self.spouse_service_branch,
                self.spouse_rank,
                self.spouse_years_of_service
            ]
            completed += sum(1 for f in spouse_fields if is_filled(f))
            total += len(spouse_fields)

        return int((completed / total) * 100) if total > 0 else 0

    def get_verification_badge_class(self) -> str:
        if self.verification_status == 'approved' or self.is_verified:
            return 'badge bg-success'
        elif self.verification_status == 'pending':
            return 'badge bg-warning'
        elif self.verification_status == 'rejected':
            return 'badge bg-danger'
        else:
            return 'badge bg-secondary'

    # ==========================
    # Display Helpers
    # ==========================

    def get_service_branch_display(self):  # NEW
        """Return human readable branch name."""
        if not self.service_branch:
            return "Not specified"

        return self.SERVICE_BRANCHES.get(
            self.service_branch.lower(),
            self.service_branch
        )

    # ==========================
    # Boost Features
    # ==========================

    def boost_profile(self, days: int = 7):
        now = datetime.utcnow()
        if self.profile_boosted_until and self.profile_boosted_until > now:
            self.profile_boosted_until += timedelta(days=days)
        else:
            self.profile_boosted_until = now + timedelta(days=days)
        db.session.commit()

    def is_boosted(self) -> bool:
        return self.profile_boosted_until is not None and self.profile_boosted_until > datetime.utcnow()

    def boost_days_remaining(self) -> int:
        if not self.is_boosted():
            return 0
        delta = self.profile_boosted_until - datetime.utcnow()
        return max(delta.days, 0)

    def __repr__(self):
        username = getattr(self.user, "username", "unknown")
        return f'<VeteranProfile {username}>'