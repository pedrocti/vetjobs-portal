from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, case
from datetime import datetime, timedelta
import os
from decimal import Decimal
from . import admin_bp

# Import shared database and models
from .stats import get_admin_stats
from app import db
from models import (
    User, VeteranProfile, EmployerProfile, Partner,
    JobPosting, JobApplication, Payment, Subscription,
    PaymentSetting, EmailSetting, Message, Testimonial
)


# ===================== MESSAGING SYSTEM =====================

@admin_bp.route('/messages')
@login_required
def messages():
    """Admin messaging system main page."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Get recent messages
    recent_messages = Message.query.filter_by(sender_id=current_user.id).order_by(desc(Message.created_at)).limit(20).all()

    # Statistics
    total_messages = Message.query.filter_by(sender_id=current_user.id).count()
    unread_count = Message.query.filter_by(sender_id=current_user.id, is_read=False).count()

    # Get user counts for recipient selection
    veteran_count = User.query.filter_by(user_type='veteran', active=True).count()
    employer_count = User.query.filter_by(user_type='employer', active=True).count()

    return render_template('admin/messages.html',
                         messages=recent_messages,
                         total_messages=total_messages,
                         unread_count=unread_count,
                         veteran_count=veteran_count,
                         employer_count=employer_count)

@admin_bp.route('/messages/compose')
@login_required
def compose_message():
    """Compose new message form."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Get users for recipient selection
    veterans = User.query.filter_by(user_type='veteran', active=True).order_by(User.first_name, User.last_name).all()
    employers = User.query.filter_by(user_type='employer', active=True).order_by(User.first_name, User.last_name).all()

    return render_template('admin/compose_message.html',
                         veterans=veterans,
                         employers=employers)

@admin_bp.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    """Send message to recipients - Simplified version to prevent hanging."""
    print("=== SEND MESSAGE ROUTE STARTED ===")

    # Basic access check
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Extract form data
    recipient_type = request.form.get('recipient_type', '')
    specific_user = request.form.get('specific_user', '')
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    priority = request.form.get('priority', 'normal')

    print(f"Form data: recipient_type={recipient_type}, subject='{subject}', priority={priority}")

    # Basic validation
    if not subject or not body:
        flash('Subject and message body are required.', 'error')
        return redirect(url_for('admin.compose_message'))

    # Determine recipients - simplified approach
    recipients = []
    try:
        if recipient_type == 'all':
            recipients = User.query.filter(User.user_type.in_(['veteran', 'employer']), User.active == True).all()
        elif recipient_type == 'veterans':
            recipients = User.query.filter_by(user_type='veteran', active=True).all()
        elif recipient_type == 'employers':
            recipients = User.query.filter_by(user_type='employer', active=True).all()
        elif recipient_type == 'specific' and specific_user:
            user = User.query.get(int(specific_user))
            if user and user.active:
                recipients = [user]

        print(f"Found {len(recipients)} recipients")

    except Exception as e:
        print(f"Error finding recipients: {e}")
        flash('Error finding recipients. Please try again.', 'error')
        return redirect(url_for('admin.compose_message'))

    if not recipients:
        flash('No valid recipients selected.', 'error')
        return redirect(url_for('admin.compose_message'))

    # Create messages - simplified
    messages_created = 0
    try:
        for recipient in recipients:
            message = Message(
                sender_id=current_user.id,
                recipient_id=recipient.id,
                subject=subject,
                body=body,
                priority=priority
            )
            db.session.add(message)
            messages_created += 1

        # Commit to database
        db.session.commit()
        print(f"Successfully created {messages_created} messages")

        flash(f'Successfully sent message to {messages_created} recipient(s).', 'success')

    except Exception as e:
        print(f"Database error: {e}")
        db.session.rollback()
        flash(f'Database error: {str(e)}', 'error')

    print("=== SEND MESSAGE ROUTE COMPLETED ===")
    return redirect(url_for('admin.messages'))

@admin_bp.route('/messages/<int:message_id>')
@login_required
def view_message(message_id):
    """View specific message details."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    message = Message.query.filter_by(id=message_id, sender_id=current_user.id).first()
    if not message:
        flash('Message not found.', 'error')
        return redirect(url_for('admin.messages'))

    return render_template('admin/view_message.html', message=message)



# Email Settings Routes

@admin_bp.route('/email-settings')
@login_required
def email_settings():
    """Admin email/SMTP settings management."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    try:
        # Initialize default settings if they don't exist
        EmailSetting.initialize_defaults(current_user.id)

        # Get all email settings
        settings = EmailSetting.query.all()

        # Convert to dictionary for easy access
        settings_dict = {}
        for setting in settings:
            settings_dict[setting.setting_key] = {
                'value': setting.setting_value,
                'description': setting.description,
                'type': setting.setting_type,
                'updated_at': setting.updated_at
            }

        # Get comprehensive admin stats for sidebar
        stats = get_admin_stats()

        return render_template('admin/email_settings.html', settings=settings_dict, stats=stats)

    except Exception as e:
        current_app.logger.error(f"Error loading email settings: {e}")
        flash('Error loading email settings. Please try again.', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/email-settings/update', methods=['POST'])
@login_required
def update_email_settings():
    """Update email/SMTP settings."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    try:
        updated_settings = []
        current_app.logger.info(f"Processing email settings update. Updated fields count: {len([k for k, v in request.form.items() if v.strip()])}")

        # Update SMTP enabled status
        smtp_enabled = request.form.get('smtp_enabled') == 'on'
        EmailSetting.set_setting('smtp_enabled', 'true' if smtp_enabled else 'false', current_user.id, 
                                'Enable SMTP email delivery', 'boolean')
        updated_settings.append('SMTP enabled')

        # Update SMTP host
        smtp_host = request.form.get('smtp_host')
        if smtp_host is not None:  # Allow empty values for clearing
            EmailSetting.set_setting('smtp_host', smtp_host, current_user.id, 
                                   'SMTP server hostname (e.g., smtp.gmail.com)', 'text')
            updated_settings.append('SMTP host')

        # Update SMTP port
        smtp_port = request.form.get('smtp_port')
        if smtp_port and smtp_port.strip():
            EmailSetting.set_setting('smtp_port', smtp_port, current_user.id, 
                                   'SMTP server port (587 for TLS, 465 for SSL)', 'number')
            updated_settings.append('SMTP port')

        # Update TLS setting
        smtp_use_tls = request.form.get('smtp_use_tls') == 'on'
        EmailSetting.set_setting('smtp_use_tls', 'true' if smtp_use_tls else 'false', current_user.id, 
                                'Use TLS encryption', 'boolean')
        updated_settings.append('TLS setting')

        # Update SMTP username
        smtp_username = request.form.get('smtp_username')
        if smtp_username is not None:  # Allow empty values for clearing
            EmailSetting.set_setting('smtp_username', smtp_username, current_user.id, 
                                   'SMTP username/email', 'text')
            updated_settings.append('SMTP username')

        # Update SMTP password
        smtp_password = request.form.get('smtp_password')
        if smtp_password is not None:  # Allow empty values for clearing
            EmailSetting.set_setting('smtp_password', smtp_password, current_user.id, 
                                   'SMTP password', 'password', encrypt=True)
            updated_settings.append('SMTP password')

        # Update from email
        from_email = request.form.get('from_email')
        if from_email is not None:
            EmailSetting.set_setting('from_email', from_email, current_user.id, 
                                   'From email address', 'text')
            updated_settings.append('from email')

        # Update from name
        from_name = request.form.get('from_name')
        if from_name is not None:
            EmailSetting.set_setting('from_name', from_name, current_user.id, 
                                   'From name displayed in emails', 'text')
            updated_settings.append('from name')

        # Update test email
        test_email = request.form.get('test_email')
        if test_email is not None:
            EmailSetting.set_setting('test_email', test_email, current_user.id, 
                                   'Test email address for sending test emails', 'text')
            updated_settings.append('test email')

        db.session.commit()

        if updated_settings:
            flash(f'Email settings updated successfully: {", ".join(updated_settings)}', 'success')
        else:
            flash('No changes were made to email settings.', 'info')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating email settings: {str(e)}")
        flash(f'An error occurred while updating settings: {str(e)}', 'error')

    return redirect(url_for('admin.email_settings'))


@admin_bp.route('/email-settings/test', methods=['POST'])
@login_required
def test_email_settings():
    """Send a test email to verify SMTP configuration."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    try:
        from services.email_service import EmailService

        # Get test email address
        test_email = EmailSetting.get_setting('test_email')
        if not test_email:
            flash('Please configure a test email address first.', 'error')
            return redirect(url_for('admin.email_settings'))

        # Initialize email service and send test email
        email_service = EmailService()

        subject = 'Test Email - SMTP Configuration'
        body = '''
        <h2>SMTP Configuration Test</h2>
        <p>This is a test email to verify your SMTP settings are working correctly.</p>
        <p>If you receive this email, your SMTP configuration is successful!</p>
        <hr>
        <p><small>Sent from Veteran-Employer Job Portal Admin Dashboard</small></p>
        '''

        success = email_service.send_email(
            to_email=test_email,
            subject=subject,
            html_content=body
        )

        if success:
            flash(f'Test email sent successfully to {test_email}', 'success')
            current_app.logger.info(f"Test email sent successfully to {test_email}")
        else:
            flash('Failed to send test email. Please check your SMTP settings.', 'error')
            current_app.logger.error("Failed to send test email")

    except Exception as e:
        current_app.logger.error(f"Error sending test email: {str(e)}")
        flash(f'Error sending test email: {str(e)}', 'error')

    return redirect(url_for('admin.email_settings'))