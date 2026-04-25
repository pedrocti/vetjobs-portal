from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum


class EmailSetting(db.Model):
    """Admin-configurable email/SMTP settings."""
    id = db.Column(db.Integer, primary_key=True)

    # Setting details
    setting_key = db.Column(db.String(50), unique=True, nullable=False)
    setting_value = db.Column(db.String(500), nullable=False)  # Longer for encrypted passwords
    setting_type = db.Column(db.String(20), default='text')  # 'text', 'number', 'boolean', 'password'
    description = db.Column(db.Text)
    is_encrypted = db.Column(db.Boolean, default=False)  # For sensitive data like passwords

    # Admin tracking
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    admin = db.relationship('User', backref=db.backref('email_settings', lazy=True))

    def __repr__(self):
        return f'<EmailSetting {self.setting_key}>'

    @classmethod
    def get_setting(cls, key, default=None):
        """Get an email setting value."""
        setting = cls.query.filter_by(setting_key=key).first()
        if setting:
            if setting.setting_type == 'number':
                try:
                    return int(setting.setting_value)
                except ValueError:
                    return default
            elif setting.setting_type == 'boolean':
                return setting.setting_value.lower() in ['true', '1', 'yes']
            elif setting.setting_type == 'password' and setting.is_encrypted:
                # In a real app, decrypt the password here
                return setting.setting_value
            return setting.setting_value
        return default

    @classmethod
    def set_setting(cls, key, value, admin_id, description=None, setting_type='text', encrypt=False):
        """Set or update an email setting."""
        setting = cls.query.filter_by(setting_key=key).first()
        if setting:
            # In a real app, encrypt sensitive values here if encrypt=True
            setting.setting_value = str(value)
            setting.updated_by = admin_id
            setting.updated_at = datetime.utcnow()
            setting.is_encrypted = encrypt
            if description:
                setting.description = description
        else:
            setting = cls(
                setting_key=key,
                setting_value=str(value),
                description=description,
                setting_type=setting_type,
                is_encrypted=encrypt,
                updated_by=admin_id
            )
            db.session.add(setting)
        return setting

    @classmethod
    def initialize_defaults(cls, admin_id):
        """Initialize default email settings if they don't exist."""
        defaults = {
            'smtp_enabled': {'value': 'false', 'description': 'Enable SMTP email delivery', 'type': 'boolean'},
            'smtp_host': {'value': '', 'description': 'SMTP server hostname (e.g., smtp.gmail.com)', 'type': 'text'},
            'smtp_port': {'value': '587', 'description': 'SMTP server port (587 for TLS, 465 for SSL)', 'type': 'number'},
            'smtp_use_tls': {'value': 'true', 'description': 'Use TLS encryption', 'type': 'boolean'},
            'smtp_username': {'value': '', 'description': 'SMTP username/email', 'type': 'text'},
            'smtp_password': {'value': '', 'description': 'SMTP password', 'type': 'password', 'encrypt': True},
            'from_email': {'value': 'noreply@veteranportal.com', 'description': 'From email address', 'type': 'text'},
            'from_name': {'value': 'Veteran-Employer Job Portal', 'description': 'From name displayed in emails', 'type': 'text'},
            'test_email': {'value': '', 'description': 'Test email address for sending test emails', 'type': 'text'}
        }

        for key, config in defaults.items():
            existing = cls.query.filter_by(setting_key=key).first()
            if not existing:
                cls.set_setting(
                    key=key,
                    value=config['value'],
                    admin_id=admin_id,
                    description=config['description'],
                    setting_type=config['type'],
                    encrypt=config.get('encrypt', False)
                )

        db.session.commit()
        return True