from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum


class PaymentSetting(db.Model):
    """Admin-configurable payment settings and fees."""
    id = db.Column(db.Integer, primary_key=True)

    # Setting details
    setting_key = db.Column(db.String(50), unique=True, nullable=False)
    setting_value = db.Column(db.String(255), nullable=False)
    setting_type = db.Column(db.String(20), default='text')  # 'text', 'number', 'boolean'
    description = db.Column(db.Text)

    # Admin tracking
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    admin = db.relationship('User', backref=db.backref('payment_settings', lazy=True))

    def __repr__(self):
        return f'<PaymentSetting {self.setting_key}>'

    @classmethod
    def get_setting(cls, key, default=None):
        """Get a payment setting value."""
        setting = cls.query.filter_by(setting_key=key).first()
        if setting:
            if setting.setting_type == 'number':
                try:
                    return float(setting.setting_value)
                except ValueError:
                    return default
            elif setting.setting_type == 'boolean':
                return setting.setting_value.lower() in ['true', '1', 'yes']
            return setting.setting_value
        return default

    @classmethod
    def set_setting(cls, key, value, admin_id, description=None, setting_type='text'):
        """Set or update a payment setting."""
        setting = cls.query.filter_by(setting_key=key).first()
        if setting:
            setting.setting_value = str(value)
            setting.updated_by = admin_id
            setting.updated_at = datetime.utcnow()
            if description:
                setting.description = description
        else:
            setting = cls(
                setting_key=key,
                setting_value=str(value),
                description=description,
                setting_type=setting_type,
                updated_by=admin_id
            )
            db.session.add(setting)
        return setting

    @classmethod
    def initialize_defaults(cls, admin_id):
        """Initialize default payment settings if they don't exist."""
        defaults = {
            # =============================
            # 🧩 Core Fees
            # =============================
            'verification_fee': {
                'value': '2000',
                'description': 'Fee charged for veteran account verification',
                'type': 'number'
            },
            'boost_fee': {
                'value': '1000',
                'description': 'Fee charged for 7-day profile boost',
                'type': 'number'
            },

            # =============================
            # 💼 Employer Subscription Plans
            # =============================
            'starter_plan_amount': {
                'value': '20000',
                'description': 'Monthly fee for Employer Starter Plan',
                'type': 'number'
            },
            'professional_plan_amount': {
                'value': '40000',
                'description': 'Monthly fee for Employer Professional Plan',
                'type': 'number'
            },
            'enterprise_plus_plan_amount': {
                'value': '120000',
                'description': 'Monthly fee for Employer Enterprise Plus Plan',
                'type': 'number'
            },

            # =============================
            # 🏫 Training Partner Plans
            # =============================
            'pro_plan_amount': {
                'value': '50000',
                'description': 'Annual fee for Training Partner Pro plan',
                'type': 'number'
            },
            'premium_plan_amount_tp': {
                'value': '80000',
                'description': 'Annual fee for Training Partner Premium plan',
                'type': 'number'
            },

            # =============================
            # ✨ FEATURE FEES (IMPORTANT)
            # =============================
            'resume_fee': {
                'value': '3000',
                'description': 'AI Resume generation fee',
                'type': 'number'
            },
            'review_fee': {
                'value': '4000',
                'description': 'Professional CV review fee',
                'type': 'number'
            },
            'ai_flyer_fee': {
                'value': '2000',
                'description': 'AI flyer generation fee',
                'type': 'number'
            },

            # ✅ THIS FIXES YOUR CURRENT ERROR
            'cv_optimization_fee': {
                'value': '5000',
                'description': 'Professional CV optimization service fee',
                'type': 'number'
            },

            # =============================
            # 🏦 Payment Gateway
            # =============================
            'payment_gateway': {
                'value': 'paystack',
                'description': 'Primary payment gateway: paystack or flutterwave',
                'type': 'text'
            },
            'paystack_mode': {
                'value': 'test',
                'description': 'Paystack mode: test or live',
                'type': 'text'
            },
            'paystack_public_key_test': {'value': '', 'description': 'Paystack test public key', 'type': 'text'},
            'paystack_secret_key_test': {'value': '', 'description': 'Paystack test secret key', 'type': 'text'},
            'paystack_public_key_live': {'value': '', 'description': 'Paystack live public key', 'type': 'text'},
            'paystack_secret_key_live': {'value': '', 'description': 'Paystack live secret key', 'type': 'text'},

            'flutterwave_mode': {
                'value': 'test',
                'description': 'Flutterwave mode: test or live',
                'type': 'text'
            },
            'flutterwave_public_key_test': {'value': '', 'description': 'Flutterwave test public key', 'type': 'text'},
            'flutterwave_secret_key_test': {'value': '', 'description': 'Flutterwave test secret key', 'type': 'text'},
            'flutterwave_public_key_live': {'value': '', 'description': 'Flutterwave live public key', 'type': 'text'},
            'flutterwave_secret_key_live': {'value': '', 'description': 'Flutterwave live secret key', 'type': 'text'},
        }

        for key, config in defaults.items():
            if not cls.query.filter_by(setting_key=key).first():
                cls.set_setting(
                    key,
                    config['value'],
                    admin_id,
                    config['description'],
                    config['type']
                )

        return True