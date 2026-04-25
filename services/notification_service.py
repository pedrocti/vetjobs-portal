import os
from datetime import datetime, timedelta
from flask import current_app, url_for
from models import Notification, NotificationPreference, User, db
from services.email_service import EmailService
from services.sms_service import SMSService

class NotificationService:
    """Service for managing notifications across all channels"""
    
    def __init__(self):
        self.email_service = None
        self.sms_service = None
    
    def _init_services(self):
        """Initialize services lazily within app context"""
        if self.email_service is None:
            self.email_service = EmailService()
        if self.sms_service is None:
            self.sms_service = SMSService()
    
    def send_notification(self, user_id, category, title, message,
                         priority='normal', send_email=True, send_sms=False,
                         related_object_type=None, related_object_id=None,
                         action_url=None, action_text=None, expires_at=None):
        """
        Send a comprehensive notification to a user
        
        Args:
            user_id: ID of the user to notify
            category: Notification category (verification, job_match, etc.)
            title: Notification title
            message: Notification message
            priority: Priority level (low, normal, high, urgent)
            send_email: Whether to send email notification
            send_sms: Whether to send SMS notification
            related_object_type: Type of related object (job, application, etc.)
            related_object_id: ID of related object
            action_url: URL for action button
            action_text: Text for action button
            expires_at: When notification expires
        """
        
        # Get user preferences
        user = User.query.get(user_id)
        if not user:
            return None
        
        preferences = NotificationPreference.get_or_create(user_id)
        
        # Create in-app notification
        notification = Notification.create_notification(
            user_id=user_id,
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
        
        # Initialize services if needed
        self._init_services()
        
        # Send email if enabled and user allows it
        if send_email and preferences.email_notifications:
            if self._should_send_email(category, preferences):
                try:
                    email_sent = self.email_service.send_notification_email(
                        user=user,
                        subject=title,
                        body=message,
                        action_url=action_url,
                        action_text=action_text,
                        category=category
                    )
                    
                    if email_sent:
                        notification.email_sent = True
                        notification.email_sent_at = datetime.utcnow()
                        db.session.commit()
                        
                except Exception as e:
                    current_app.logger.error(f"Failed to send email notification: {e}")
        
        # Send SMS if enabled and user allows it
        if send_sms and preferences.sms_notifications:
            if self._should_send_sms(category, priority, preferences):
                try:
                    sms_sent = self.sms_service.send_notification_sms(
                        phone_number=preferences.phone_number or user.phone,
                        message=f"{title}: {message}",
                        category=category
                    )
                    
                    if sms_sent:
                        notification.sms_sent = True
                        notification.sms_sent_at = datetime.utcnow()
                        db.session.commit()
                        
                except Exception as e:
                    current_app.logger.error(f"Failed to send SMS notification: {e}")
        
        return notification
    
    def _should_send_email(self, category, preferences):
        """Determine if email should be sent based on category and preferences"""
        email_settings = {
            'job_match': preferences.email_job_matches,
            'application': preferences.email_applications,
            'payment': preferences.email_payments,
            'subscription': preferences.email_payments,
            'verification': preferences.email_notifications,
            'profile_view': preferences.email_notifications,
            'system': preferences.email_notifications,
            'announcement': preferences.email_notifications
        }
        
        return email_settings.get(category, preferences.email_notifications)
    
    def _should_send_sms(self, category, priority, preferences):
        """Determine if SMS should be sent based on category, priority and preferences"""
        # Only send SMS for urgent notifications if user has urgent-only setting
        if preferences.sms_urgent_only and priority != 'urgent':
            return False
        
        # Check category-specific settings
        sms_settings = {
            'payment': preferences.sms_payments,
            'subscription': preferences.sms_payments,
            'security': True,  # Always send security notifications
            'verification': priority in ['high', 'urgent']
        }
        
        return sms_settings.get(category, priority == 'urgent')
    
    # Specific notification methods for different events
    
    def notify_veteran_verified(self, user_id):
        """Notify veteran that their account has been verified"""
        return self.send_notification(
            user_id=user_id,
            category='verification',
            title='Account Verified Successfully!',
            message='Congratulations! Your veteran status has been verified. You can now access all job listings and apply for positions.',
            priority='high',
            send_email=True,
            action_url=url_for('jobs.job_board'),
            action_text='Browse Jobs'
        )
    
    def notify_job_match(self, user_id, job_title, job_id):
        """Notify veteran about a new job match"""
        return self.send_notification(
            user_id=user_id,
            category='job_match',
            title='New Job Match Found!',
            message=f'A new position "{job_title}" matches your skills and preferences.',
            priority='normal',
            send_email=True,
            related_object_type='job',
            related_object_id=job_id,
            action_url=url_for('jobs.view_job', job_id=job_id),
            action_text='View Job'
        )
    
    def notify_profile_viewed(self, user_id, employer_name):
        """Notify veteran that an employer viewed their profile"""
        return self.send_notification(
            user_id=user_id,
            category='profile_view',
            title='Profile Viewed by Employer',
            message=f'{employer_name} viewed your profile. They might be interested in your skills!',
            priority='normal',
            send_email=False  # Don't email for profile views by default
        )
    
    def notify_application_received(self, employer_id, veteran_name, job_title, application_id):
        """Notify employer about a new job application"""
        return self.send_notification(
            user_id=employer_id,
            category='application',
            title='New Job Application Received',
            message=f'{veteran_name} has applied for your "{job_title}" position.',
            priority='normal',
            send_email=True,
            related_object_type='application',
            related_object_id=application_id,
            action_url=url_for('applications.view_application', application_id=application_id),
            action_text='Review Application'
        )
    
    def notify_application_status_change(self, user_id, job_title, status, employer_message=None):
        """Notify veteran about application status change"""
        status_messages = {
            'accepted': f'Great news! Your application for "{job_title}" has been accepted.',
            'rejected': f'Unfortunately, your application for "{job_title}" was not selected this time.',
            'interview': f'You\'ve been invited for an interview for the "{job_title}" position!',
            'withdrawn': f'Your application for "{job_title}" has been withdrawn.'
        }
        
        message = status_messages.get(status, f'Your application status for "{job_title}" has been updated to {status}.')
        if employer_message:
            message += f' Message from employer: {employer_message}'
        
        priority = 'high' if status in ['accepted', 'interview'] else 'normal'
        
        return self.send_notification(
            user_id=user_id,
            category='application',
            title='Application Status Update',
            message=message,
            priority=priority,
            send_email=True
        )
    
    def notify_payment_success(self, user_id, amount, payment_type, reference):
        """Notify user about successful payment"""
        return self.send_notification(
            user_id=user_id,
            category='payment',
            title='Payment Successful',
            message=f'Your payment of ₦{amount:,.2f} for {payment_type} has been processed successfully. Reference: {reference}',
            priority='normal',
            send_email=True,
            send_sms=True,
            related_object_type='payment',
            related_object_id=reference,
            action_url=url_for('payments.payment_history'),
            action_text='View Receipt'
        )
    
    def notify_payment_failed(self, user_id, amount, payment_type, reason):
        """Notify user about failed payment"""
        return self.send_notification(
            user_id=user_id,
            category='payment',
            title='Payment Failed',
            message=f'Your payment of ₦{amount:,.2f} for {payment_type} could not be processed. Reason: {reason}',
            priority='high',
            send_email=True,
            send_sms=True
        )
    
    def notify_subscription_expiring(self, user_id, plan_type, days_left):
        """Notify employer about expiring subscription"""
        return self.send_notification(
            user_id=user_id,
            category='subscription',
            title='Subscription Expiring Soon',
            message=f'Your {plan_type} subscription will expire in {days_left} days. Renew now to continue enjoying premium features.',
            priority='high',
            send_email=True,
            action_url=url_for('payments.employer_subscription_plans'),
            action_text='Renew Subscription'
        )
    
    def notify_subscription_expired(self, user_id, plan_type):
        """Notify employer about expired subscription"""
        return self.send_notification(
            user_id=user_id,
            category='subscription',
            title='Subscription Expired',
            message=f'Your {plan_type} subscription has expired. Your account has been downgraded to the Free plan.',
            priority='urgent',
            send_email=True,
            send_sms=True,
            action_url=url_for('payments.employer_subscription_plans'),
            action_text='Reactivate Subscription'
        )
    
    def notify_admin_new_registration(self, admin_user_id, new_user_name, user_type):
        """Notify admin about new user registration"""
        return self.send_notification(
            user_id=admin_user_id,
            category='system',
            title='New User Registration',
            message=f'A new {user_type} "{new_user_name}" has registered on the platform.',
            priority='low',
            send_email=False  # Admins can check dashboard
        )
    
    def notify_admin_verification_completed(self, admin_user_id, veteran_name):
        """Notify admin about completed verification"""
        return self.send_notification(
            user_id=admin_user_id,
            category='verification',
            title='Veteran Verification Completed',
            message=f'Verification payment received from {veteran_name}. Please review and approve their veteran status.',
            priority='normal',
            send_email=True,
            action_url=url_for('admin.manage_veteran_profiles'),
            action_text='Review Verification'
        )
    
    def notify_admin_payment_failed(self, admin_user_id, user_name, amount, payment_type):
        """Notify admin about failed payment"""
        return self.send_notification(
            user_id=admin_user_id,
            category='payment',
            title='Payment Failed - Admin Alert',
            message=f'Payment failure: {user_name} - ₦{amount:,.2f} for {payment_type}. Manual review may be required.',
            priority='high',
            send_email=True
        )
    
    def get_user_notifications(self, user_id, limit=50, include_read=True):
        """Get notifications for a user"""
        query = Notification.query.filter_by(user_id=user_id)
        
        if not include_read:
            query = query.filter_by(is_read=False)
        
        # Filter out expired notifications
        query = query.filter(
            db.or_(
                Notification.expires_at.is_(None),
                Notification.expires_at > datetime.utcnow()
            )
        )
        
        return query.order_by(Notification.created_at.desc()).limit(limit).all()
    
    def mark_notification_read(self, notification_id, user_id):
        """Mark a specific notification as read"""
        notification = Notification.query.filter_by(
            id=notification_id, 
            user_id=user_id
        ).first()
        
        if notification:
            notification.mark_as_read()
            return True
        return False
    
    def mark_all_notifications_read(self, user_id):
        """Mark all notifications as read for a user"""
        return Notification.mark_all_as_read(user_id)
    
    def get_unread_count(self, user_id):
        """Get unread notification count for a user"""
        return Notification.get_unread_count(user_id)
    
    def cleanup_expired_notifications(self):
        """Clean up expired notifications (run as background task)"""
        expired_notifications = Notification.query.filter(
            Notification.expires_at < datetime.utcnow()
        ).all()
        
        count = len(expired_notifications)
        for notification in expired_notifications:
            db.session.delete(notification)
        
        db.session.commit()
        return count


# Create global instance
notification_service = NotificationService()