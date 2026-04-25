from app import db
from datetime import datetime
from sqlalchemy import func, or_

from .user import User


class Notification(db.Model):
    """Model for storing user notifications"""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    notification_type = db.Column(db.String(50), nullable=False)  # system, email, sms
    category = db.Column(db.String(50), nullable=False)  # verification, job_match, etc.
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)

    is_read = db.Column(db.Boolean, default=False, nullable=False)
    priority = db.Column(db.String(20), default='normal', nullable=False)

    # Related object metadata
    related_object_type = db.Column(db.String(50))
    related_object_id = db.Column(db.Integer)

    # Action button
    action_url = db.Column(db.String(500))
    action_text = db.Column(db.String(100))

    # Delivery tracking
    email_sent = db.Column(db.Boolean, default=False, nullable=False)
    email_sent_at = db.Column(db.DateTime)
    sms_sent = db.Column(db.Boolean, default=False, nullable=False)
    sms_sent_at = db.Column(db.DateTime)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    # FIXED: safer ordering (no string-based order_by)
    user = db.relationship(
        'User',
        backref=db.backref(
            'notifications',
            lazy='dynamic',
            order_by=lambda: Notification.created_at.desc()
        )
    )

    # -------------------------
    # Core methods
    # -------------------------
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
            db.session.commit()

    def is_expired(self):
        return self.expires_at and datetime.utcnow() > self.expires_at

    # -------------------------
    # UI helpers
    # -------------------------
    @property
    def formatted_created_at(self):
        now = datetime.utcnow()
        diff = now - self.created_at

        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        if diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        if diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        return "Just now"

    @property
    def priority_class(self):
        return {
            'low': 'text-muted',
            'normal': 'text-dark',
            'high': 'text-warning',
            'urgent': 'text-danger'
        }.get(self.priority, 'text-dark')

    @property
    def category_icon(self):
        return {
            'verification': 'fas fa-shield-alt',
            'job_match': 'fas fa-briefcase',
            'application': 'fas fa-file-alt',
            'payment': 'fas fa-credit-card',
            'subscription': 'fas fa-crown',
            'profile_view': 'fas fa-eye',
            'system': 'fas fa-info-circle',
            'security': 'fas fa-lock',
            'announcement': 'fas fa-bullhorn'
        }.get(self.category, 'fas fa-bell')

    # -------------------------
    # CRUD helpers
    # -------------------------
    @staticmethod
    def create_notification(
        user_id,
        category,
        title,
        message,
        notification_type='system',
        priority='normal',
        related_object_type=None,
        related_object_id=None,
        action_url=None,
        action_text=None,
        expires_at=None
    ):
        notification = Notification(
            user_id=user_id,
            notification_type=notification_type,
            category=category,
            title=title,
            message=message,
            priority=priority,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            action_url=action_url,
            action_text=action_text,
            expires_at=expires_at
        )

        db.session.add(notification)
        db.session.commit()
        return notification

    @staticmethod
    def get_unread_count(user_id):
        return Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).filter(
            or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        ).count()

    @staticmethod
    def mark_all_as_read(user_id):
        notifications = Notification.query.filter_by(
            user_id=user_id,
            is_read=False
        ).all()

        for n in notifications:
            n.is_read = True
            n.read_at = datetime.utcnow()

        db.session.commit()
        return len(notifications)


# ======================================================
# Notification Preferences
# ======================================================
class NotificationPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

    email_notifications = db.Column(db.Boolean, default=True, nullable=False)
    email_job_matches = db.Column(db.Boolean, default=True, nullable=False)
    email_applications = db.Column(db.Boolean, default=True, nullable=False)
    email_payments = db.Column(db.Boolean, default=True, nullable=False)
    email_marketing = db.Column(db.Boolean, default=False, nullable=False)

    sms_notifications = db.Column(db.Boolean, default=False, nullable=False)
    sms_urgent_only = db.Column(db.Boolean, default=True, nullable=False)
    sms_payments = db.Column(db.Boolean, default=True, nullable=False)

    whatsapp_notifications = db.Column(db.Boolean, default=False, nullable=False)
    whatsapp_job_matches = db.Column(db.Boolean, default=False, nullable=False)

    push_notifications = db.Column(db.Boolean, default=True, nullable=False)
    sound_notifications = db.Column(db.Boolean, default=True, nullable=False)

    daily_digest = db.Column(db.Boolean, default=False, nullable=False)
    weekly_summary = db.Column(db.Boolean, default=True, nullable=False)

    phone_number = db.Column(db.String(20))
    whatsapp_number = db.Column(db.String(20))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('notification_preferences', uselist=False))

    @staticmethod
    def get_or_create(user_id):
        pref = NotificationPreference.query.filter_by(user_id=user_id).first()

        if not pref:
            pref = NotificationPreference(user_id=user_id)
            db.session.add(pref)
            db.session.commit()

        return pref


# ======================================================
# Broadcast Notifications
# ======================================================
class BroadcastNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    target_audience = db.Column(db.String(50), nullable=False)

    priority = db.Column(db.String(20), default='normal', nullable=False)

    send_email = db.Column(db.Boolean, default=False, nullable=False)
    send_sms = db.Column(db.Boolean, default=False, nullable=False)
    send_push = db.Column(db.Boolean, default=True, nullable=False)

    action_url = db.Column(db.String(500))
    action_text = db.Column(db.String(100))

    total_recipients = db.Column(db.Integer, default=0, nullable=False)
    delivered_count = db.Column(db.Integer, default=0, nullable=False)
    read_count = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    scheduled_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)

    admin_user = db.relationship('User', backref=db.backref('broadcast_notifications', lazy='dynamic'))

    def send_broadcast(self):
        from flask import current_app

        if self.target_audience == 'veterans':
            users = User.query.filter_by(user_type='veteran').all()
        elif self.target_audience == 'employers':
            users = User.query.filter_by(user_type='employer').all()
        else:
            users = User.query.filter(User.user_type.in_(['veteran', 'employer'])).all()

        self.total_recipients = len(users)

        for user in users:
            Notification.create_notification(
                user_id=user.id,
                category='announcement',
                title=self.title,
                message=self.message,
                priority=self.priority,
                action_url=self.action_url,
                action_text=self.action_text,
                related_object_type='broadcast',
                related_object_id=self.id
            )
            self.delivered_count += 1

        self.sent_at = datetime.utcnow()
        db.session.commit()

        return self.delivered_count