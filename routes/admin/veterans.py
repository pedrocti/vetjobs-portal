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

@admin_bp.route('/veterans')
@login_required
def veteran_management():
    """Comprehensive veteran management interface."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Get filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')
    verification_filter = request.args.get('verification', '')

    # Base query
    query = db.session.query(User, VeteranProfile).outerjoin(VeteranProfile, User.id == VeteranProfile.user_id).filter(User.user_type == "veteran")

    # Apply filters
    if search:
        query = query.filter(or_(
            User.full_name.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%'),
            User.username.ilike(f'%{search}%')
        ))

    if status_filter == 'active':
        query = query.filter(User.active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.active == False)

    if verification_filter == 'verified':
        query = query.filter(VeteranProfile.is_verified == True)
    elif verification_filter == 'pending':
        query = query.filter(VeteranProfile.verification_status == 'pending')
    elif verification_filter == 'rejected':
        query = query.filter(VeteranProfile.verification_status == 'rejected')

    veterans = query.order_by(desc(User.created_at)).all()

    # Calculate stats
    stats = {
        'total': User.query.filter_by(user_type='veteran').count(),
        'active': User.query.filter_by(user_type='veteran', active=True).count(),
        'verified': db.session.query(User).join(VeteranProfile, User.id == VeteranProfile.user_id).filter(
            User.user_type == 'veteran', VeteranProfile.is_verified == True).count(),
        'pending': db.session.query(User).join(VeteranProfile, User.id == VeteranProfile.user_id).filter(
            User.user_type == 'veteran', VeteranProfile.verification_status == 'pending').count()
    }

    # Add comprehensive admin stats for sidebar
    admin_stats = get_admin_stats()
    stats.update(admin_stats)

    return render_template('admin/veteran_management.html', 
                         veterans=veterans, 
                         stats=stats,
                         current_filters={
                             'search': search,
                             'status': status_filter,
                             'verification': verification_filter
                         })