from app import db
from datetime import datetime, timedelta


class Subscription(db.Model):
    """Employer subscription plans and management."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # Core plan info
    plan_type = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='active')

    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='NGN')
    billing_cycle = db.Column(db.String(20), default='monthly')

    started_at = db.Column(db.DateTime, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    renewed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    # Paystack
    paystack_customer_code = db.Column(db.String(100))
    paystack_subscription_code = db.Column(db.String(100))
    paystack_email_token = db.Column(db.String(100))

    # Renewal
    auto_renew = db.Column(db.Boolean, default=True)
    next_payment_date = db.Column(db.DateTime)

    # Plan features (NON-SECURITY ONLY)
    max_job_posts = db.Column(db.Integer, default=5)
    can_contact_candidates = db.Column(db.Boolean, default=False)
    can_export_resumes = db.Column(db.Boolean, default=False)

    priority_support = db.Column(db.Boolean, default=False)
    featured_jobs = db.Column(db.Boolean, default=False)
    social_promotion = db.Column(db.Boolean, default=False)
    analytics_access = db.Column(db.Boolean, default=False)
    dedicated_manager = db.Column(db.Boolean, default=False)
    api_access = db.Column(db.Boolean, default=False)
    smart_candidate_matching = db.Column(db.Boolean, default=False)
    ai_talent_suggestions = db.Column(db.Boolean, default=False)
    bulk_messaging = db.Column(db.Boolean, default=False)
    job_post_notifications = db.Column(db.Boolean, default=False)
    employer_branding_page = db.Column(db.Boolean, default=False)
    job_boosts = db.Column(db.Integer, default=0)
    team_accounts = db.Column(db.Boolean, default=False)
    onboarding_training = db.Column(db.Boolean, default=False)
    quarterly_hiring_report = db.Column(db.Boolean, default=False)
    white_label_portal = db.Column(db.Boolean, default=False)
    co_branded_sponsorship = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('subscription', uselist=False))

    # =========================================================
    # 🔒 SECURITY LAYER (SINGLE SOURCE OF TRUTH - NO EXCEPTIONS)
    # =========================================================

    def is_active(self):
        return (
            self.status == 'active'
            and self.expires_at
            and self.expires_at > datetime.utcnow()
        )

    def _has_premium_access(self):
        """
        INTERNAL ONLY:
        Defines plans that can access CV system.
        """
        return self.plan_type in ['professional', 'enterprise_plus']

    def is_cv_access_granted(self):
        """
        🚨 FINAL SECURITY GATE (USE THIS IN ROUTES)
        ONLY Professional + Enterprise can access CVs.
        """
        return self.is_active() and self._has_premium_access()

    def enforce_cv_access(self):
        """
        HARD GATE (routes should check this explicitly)
        """
        return self.is_cv_access_granted()

    # =========================================================
    # 🔁 BACKWARD SAFE METHODS (DO NOT REMOVE USED TEMPLATES)
    # =========================================================

    def can_view_cv(self):
        return self.is_cv_access_granted()

    def can_view_or_download_cv(self):
        return self.is_cv_access_granted()

    def can_export_cv(self):
        return self.is_cv_access_granted()

    # =========================================================
    # 📊 BUSINESS LOGIC (NON-SECURITY FEATURES)
    # =========================================================

    def can_use_feature(self, feature_name):
        # 1. If DB explicitly enables it → allow
        if getattr(self, feature_name, False):
            return True

        # 2. fallback to plan logic
        if self.plan_type == "enterprise_plus":
            return True

        if self.plan_type == "professional":
            return feature_name in ["analytics_access", "ai_talent_suggestions"]

        return False

    def can_contact(self):
        return bool(self.can_contact_candidates) and self.is_active()

    def days_until_expiry(self):
        if not self.expires_at:
            return 0
        return max(0, (self.expires_at - datetime.utcnow()).days)

    def can_post_job(self, user_id):
        from models.jobpost import JobPosting

        if not self.is_active():
            return False

        if self.max_job_posts == -1:
            return True

        total = JobPosting.query.filter_by(
            posted_by=user_id,
            is_active=True
        ).count()

        return total < self.max_job_posts

    # =========================================================
    # 🧠 PLAN CONFIGURATION (PRICING + FEATURES)
    # =========================================================

    @classmethod
    def get_plan_features(cls, plan_type):
        plans = {
            'free': {
                'max_job_posts': 1,
                'can_contact_candidates': False,
                'can_export_resumes': False,
                'job_boosts': 0,
                'analytics_access': False,
                'team_accounts': False,
                'smart_candidate_matching': False,
                'ai_talent_suggestions': False,
                'priority_support': False,
                'dedicated_manager': False,
                'amount': 0,
                'name': 'Free Plan'
            },

            'starter': {
                'max_job_posts': 3,
                'can_contact_candidates': False,
                'can_export_resumes': False,
                'job_boosts': 0,
                'analytics_access': False,
                'team_accounts': False,
                'smart_candidate_matching': False,
                'ai_talent_suggestions': False,
                'priority_support': False,
                'dedicated_manager': False,
                'amount': 15000,
                'name': 'Starter Plan'
            },

            'professional': {
                'max_job_posts': -1,
                'can_contact_candidates': True,
                'can_export_resumes': True,
                'smart_candidate_matching': True,
                'ai_talent_suggestions': True,
                'job_boosts': 2,
                'analytics_access': True,
                'team_accounts': False,
                'priority_support': True,
                'amount': 49000,
                'name': 'Professional Plan'
            },

            'enterprise_plus': {
                'max_job_posts': -1,
                'can_contact_candidates': True,
                'can_export_resumes': True,
                'smart_candidate_matching': True,
                'ai_talent_suggestions': True,
                'job_boosts': 5,
                'analytics_access': True,
                'team_accounts': True,
                'priority_support': True,
                'dedicated_manager': True,
                'amount': 99000,
                'name': 'Enterprise Plan'
            }
        }

        return plans.get(plan_type, plans['starter'])

    # =========================================================
    # 🏗️ SUBSCRIPTION CREATION (SAFE)
    # =========================================================

    @classmethod
    def create_for_user(cls, user, plan_type="free", billing_cycle="monthly", auto_renew=False):

        features = cls.get_plan_features(plan_type)
        now = datetime.utcnow()

        duration_map = {
            "monthly": 30,
            "6_months": 182,
            "yearly": 365
        }

        billing_cycle = billing_cycle if billing_cycle in duration_map else "monthly"

        discount_map = {
            "monthly": 0,
            "6_months": 0.10,
            "yearly": 0.20
        }

        base_amount = features.get('amount', 0)
        final_amount = base_amount * (1 - discount_map.get(billing_cycle, 0))

        # ❌ DO NOT unpack feature dictionary into model
        sub = cls(
            user_id=user.id,
            plan_type=plan_type,
            status="active",
            amount=final_amount,
            billing_cycle=billing_cycle,
            started_at=now,
            expires_at=now + timedelta(days=duration_map[billing_cycle]),
            auto_renew=auto_renew,
            next_payment_date=now + timedelta(days=duration_map[billing_cycle]),

            # ONLY REAL MODEL FIELDS BELOW
            max_job_posts=features.get("max_job_posts", 1),
            can_contact_candidates=features.get("can_contact_candidates", False),
            can_export_resumes=features.get("can_export_resumes", False),
            priority_support=features.get("priority_support", False),
            featured_jobs=features.get("featured_jobs", False),
            social_promotion=features.get("social_promotion", False),
            analytics_access=features.get("analytics_access", False),
            team_accounts=features.get("team_accounts", False),
            job_boosts=features.get("job_boosts", 0),
        )

        db.session.add(sub)
        db.session.commit()
        return sub

    # =========================================================
    # 🔁 USER SUBSCRIPTION SAFETY
    # =========================================================

    @classmethod
    def get_for_user(cls, user):
        """Return the active subscription if one exists, else the most recent one."""
        active = (
            cls.query.filter_by(user_id=user.id, status='active')
            .order_by(cls.id.desc())
            .first()
        )
        if active and active.is_active():
            return active
        return cls.query.filter_by(user_id=user.id).order_by(cls.id.desc()).first()

    @classmethod
    def get_or_create_for_user(cls, user):
        """Return active subscription, else most recent, else create a free one."""
        sub = cls.get_for_user(user)
        if sub is None:
            sub = cls.create_for_user(user, plan_type="free", billing_cycle="monthly", auto_renew=False)
        return sub

    # =========================================================
    # DEBUG
    # =========================================================

    def __repr__(self):
        return f'<Subscription {self.user_id} - {self.plan_type}>'