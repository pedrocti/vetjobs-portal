from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models import Notification, NotificationPreference, BroadcastNotification, User, db
from services.notification_service import notification_service
from datetime import datetime

notifications_bp = Blueprint('notifications', __name__)

@notifications_bp.route('/')
@login_required
def notification_center():
    """Display user's notification center"""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Get user notifications with pagination
    notifications = Notification.query.filter_by(user_id=current_user.id).filter(
        db.or_(
            Notification.expires_at.is_(None),
            Notification.expires_at > datetime.utcnow()
        )
    ).order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get unread count
    unread_count = notification_service.get_unread_count(current_user.id)
    
    return render_template('notifications/center.html', 
                         notifications=notifications,
                         unread_count=unread_count)

@notifications_bp.route('/api/list')
@login_required
def api_list_notifications():
    """API endpoint to get notifications (for AJAX/WebSocket updates)"""
    limit = request.args.get('limit', 10, type=int)
    include_read = request.args.get('include_read', True, type=bool)
    
    notifications = notification_service.get_user_notifications(
        user_id=current_user.id,
        limit=limit,
        include_read=include_read
    )
    
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'category': notification.category,
            'category_icon': notification.category_icon,
            'priority': notification.priority,
            'priority_class': notification.priority_class,
            'is_read': notification.is_read,
            'formatted_created_at': notification.formatted_created_at,
            'action_url': notification.action_url,
            'action_text': notification.action_text,
            'created_at': notification.created_at.isoformat()
        })
    
    return jsonify({
        'notifications': notifications_data,
        'unread_count': notification_service.get_unread_count(current_user.id)
    })

@notifications_bp.route('/api/unread-count')
@login_required
def api_unread_count():
    """API endpoint to get unread notification count"""
    count = notification_service.get_unread_count(current_user.id)
    return jsonify({'unread_count': count})

@notifications_bp.route('/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Mark a specific notification as read"""
    success = notification_service.mark_notification_read(notification_id, current_user.id)
    
    if request.is_json:
        return jsonify({
            'success': success,
            'unread_count': notification_service.get_unread_count(current_user.id)
        })
    
    if success:
        flash('Notification marked as read.', 'success')
    else:
        flash('Notification not found.', 'error')
    
    return redirect(url_for('notifications.notification_center'))

@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    count = notification_service.mark_all_notifications_read(current_user.id)
    
    if request.is_json:
        return jsonify({
            'success': True,
            'marked_count': count,
            'unread_count': 0
        })
    
    flash(f'{count} notifications marked as read.', 'success')
    return redirect(url_for('notifications.notification_center'))

@notifications_bp.route('/preferences')
@login_required
def notification_preferences():
    """Display notification preferences"""
    preferences = NotificationPreference.get_or_create(current_user.id)
    return render_template('notifications/preferences.html', preferences=preferences)

@notifications_bp.route('/preferences', methods=['POST'])
@login_required
def update_notification_preferences():
    """Update user notification preferences"""
    preferences = NotificationPreference.get_or_create(current_user.id)
    
    try:
        # Email preferences
        preferences.email_notifications = bool(request.form.get('email_notifications'))
        preferences.email_job_matches = bool(request.form.get('email_job_matches'))
        preferences.email_applications = bool(request.form.get('email_applications'))
        preferences.email_payments = bool(request.form.get('email_payments'))
        preferences.email_marketing = bool(request.form.get('email_marketing'))
        
        # SMS preferences
        preferences.sms_notifications = bool(request.form.get('sms_notifications'))
        preferences.sms_urgent_only = bool(request.form.get('sms_urgent_only'))
        preferences.sms_payments = bool(request.form.get('sms_payments'))
        
        # WhatsApp preferences
        preferences.whatsapp_notifications = bool(request.form.get('whatsapp_notifications'))
        preferences.whatsapp_job_matches = bool(request.form.get('whatsapp_job_matches'))
        
        # In-app preferences
        preferences.push_notifications = bool(request.form.get('push_notifications'))
        preferences.sound_notifications = bool(request.form.get('sound_notifications'))
        
        # Frequency settings
        preferences.daily_digest = bool(request.form.get('daily_digest'))
        preferences.weekly_summary = bool(request.form.get('weekly_summary'))
        
        # Contact information
        preferences.phone_number = request.form.get('phone_number', '').strip()
        preferences.whatsapp_number = request.form.get('whatsapp_number', '').strip()
        
        preferences.updated_at = datetime.utcnow()
        db.session.commit()
        
        flash('Notification preferences updated successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating preferences.', 'error')
    
    return redirect(url_for('notifications.notification_preferences'))

# Admin notification routes
@notifications_bp.route('/admin/broadcast')
@login_required
def admin_broadcast_form():
    """Display broadcast notification form (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))
    
    return render_template('notifications/admin_broadcast.html')

@notifications_bp.route('/admin/broadcast', methods=['POST'])
@login_required
def admin_send_broadcast():
    """Send broadcast notification (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))
    
    try:
        title = request.form.get('title', '').strip()
        message = request.form.get('message', '').strip()
        target_audience = request.form.get('target_audience', 'all')
        priority = request.form.get('priority', 'normal')
        send_email = bool(request.form.get('send_email'))
        send_sms = bool(request.form.get('send_sms'))
        action_url = request.form.get('action_url', '').strip()
        action_text = request.form.get('action_text', '').strip()
        
        if not title or not message:
            flash('Title and message are required.', 'error')
            return redirect(url_for('notifications.admin_broadcast_form'))
        
        # Create broadcast notification
        broadcast = BroadcastNotification(
            admin_user_id=current_user.id,
            title=title,
            message=message,
            target_audience=target_audience,
            priority=priority,
            send_email=send_email,
            send_sms=send_sms,
            send_push=True,
            action_url=action_url if action_url else None,
            action_text=action_text if action_text else None
        )
        
        db.session.add(broadcast)
        db.session.commit()
        
        # Send the broadcast
        delivered_count = broadcast.send_broadcast()
        
        flash(f'Broadcast sent successfully to {delivered_count} users.', 'success')
        return redirect(url_for('notifications.admin_broadcast_history'))
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while sending broadcast.', 'error')
        return redirect(url_for('notifications.admin_broadcast_form'))

@notifications_bp.route('/admin/broadcast/history')
@login_required
def admin_broadcast_history():
    """Display broadcast history (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    broadcasts = BroadcastNotification.query.order_by(
        BroadcastNotification.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('notifications/admin_broadcast_history.html', 
                         broadcasts=broadcasts)

@notifications_bp.route('/admin/logs')
@login_required
def admin_notification_logs():
    """Display notification logs (admin only)"""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))
    
    page = request.args.get('page', 1, type=int)
    category = request.args.get('category', '')
    priority = request.args.get('priority', '')
    per_page = 50
    
    # Build query
    query = Notification.query
    
    if category:
        query = query.filter_by(category=category)
    
    if priority:
        query = query.filter_by(priority=priority)
    
    notifications = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get categories and priorities for filter dropdowns
    categories = db.session.query(Notification.category.distinct()).all()
    priorities = db.session.query(Notification.priority.distinct()).all()
    
    return render_template('notifications/admin_logs.html',
                         notifications=notifications,
                         categories=[c[0] for c in categories],
                         priorities=[p[0] for p in priorities],
                         current_category=category,
                         current_priority=priority)

# Test notification route for development
@notifications_bp.route('/test')
@login_required
def test_notification():
    """Create a test notification (development only)"""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))
    
    # Create test notification
    notification_service.send_notification(
        user_id=current_user.id,
        category='system',
        title='Test Notification',
        message='This is a test notification to verify the system is working correctly.',
        priority='normal',
        send_email=False,
        action_url=url_for('notifications.notification_center'),
        action_text='View Notifications'
    )
    
    flash('Test notification created.', 'success')
    return redirect(url_for('notifications.notification_center'))