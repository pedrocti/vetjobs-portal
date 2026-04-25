from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Optional

# 🔐 NEW: secure token system
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # Login / Auth fields
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)

    # Personal info
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)
    active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)

    # Employer-specific status
    employer_status = db.Column(db.String(20), default="pending")

    # Time tracking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Profile fields
    phone = db.Column(db.String(20), unique=True, index=True)
    location = db.Column(db.String(100))
    bio = db.Column(db.Text)
    onboarding_completed = db.Column(db.Boolean, default=False)

    # ═══════════════════════════════════════════════════════════════
    # 🔐 EMAIL VERIFICATION TOKENS (FIXED + CLEAN)
    # ═══════════════════════════════════════════════════════════════

    def _get_serializer(self):
        secret = current_app.config.get("SECRET_KEY")

        if not secret:
            raise RuntimeError("SECRET_KEY missing in config")

        return URLSafeTimedSerializer(secret)


    def generate_verification_token(self):
        serializer = self._get_serializer()

        return serializer.dumps(
            {
                "user_id": self.id,
                "email": self.email
            },
            salt="email-verify"
        )

    @staticmethod
    def verify_verification_token(token, expiration=3600):
        from models import User

        serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

        try:
            data = serializer.loads(
                token,
                salt="email-verify",
                max_age=expiration
            )
        except (SignatureExpired, BadSignature):
            return None

        return User.query.filter_by(
            id=data.get("user_id"),
            email=data.get("email")
        ).first()

    # ═══════════════════════════════════════════════════════════════
    # Password helpers
    # ═══════════════════════════════════════════════════════════════
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    # ═══════════════════════════════════════════════════════════════
    # Role helpers
    # ═══════════════════════════════════════════════════════════════
    def is_veteran(self):
        return self.user_type == "veteran"

    def is_employer(self):
        return self.user_type == "employer"

    def is_trainer(self):
        return self.user_type == "trainer"

    def is_partner(self):
        return self.user_type == "partner"

    def is_admin(self):
        return self.user_type == "admin"

    # ═══════════════════════════════════════════════════════════════
    # Employer-specific state checks
    # ═══════════════════════════════════════════════════════════════
    def is_employer_approved(self):
        return self.is_employer() and self.employer_status == "active"

    def is_employer_pending(self):
        return self.is_employer() and self.employer_status == "pending"

    def is_employer_rejected(self):
        return self.is_employer() and self.employer_status == "rejected"

    def approve_employer(self):
        """Approve employer and give them a free subscription if they don’t have one."""
        if self.is_employer():
            self.employer_status = "active"
            from models import Subscription
            if not getattr(self, "subscription", None):
                Subscription.create_for_user(self, plan_type="free")
            db.session.commit()
            return True
        return False

    def reject_employer(self):
        if self.is_employer():
            self.employer_status = "rejected"
            db.session.commit()
            return True
        return False

    def __repr__(self):
        return f"<User {self.username} ({self.user_type})>"