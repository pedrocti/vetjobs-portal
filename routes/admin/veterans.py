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

    tier_filter = request.args.get('tier', '')
    if tier_filter == 'verified':
        query = query.filter(VeteranProfile.veteran_tier == 'verified')
    elif tier_filter == 'basic':
        query = query.filter(or_(VeteranProfile.veteran_tier == 'basic', VeteranProfile.veteran_tier == None))

    veterans = query.order_by(
        case((VeteranProfile.veteran_tier == 'verified', 0), else_=1),
        desc(User.created_at)
    ).all()

    stats['job_ready'] = db.session.query(User).join(
        VeteranProfile, User.id == VeteranProfile.user_id
    ).filter(
        User.user_type == 'veteran', VeteranProfile.veteran_tier == 'verified'
    ).count()

    return render_template('admin/veteran_management.html',
                         veterans=veterans,
                         stats=stats,
                         current_filters={
                             'search': search,
                             'status': status_filter,
                             'verification': verification_filter,
                             'tier': tier_filter,
                         })


@admin_bp.route('/veterans/<int:veteran_id>/set-tier', methods=['POST'])
@login_required
def set_veteran_tier(veteran_id):
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('admin.veteran_management'))

    tier = request.form.get('tier', 'basic')
    if tier not in ('basic', 'verified'):
        flash('Invalid tier.', 'error')
        return redirect(url_for('admin.veteran_management'))

    profile = VeteranProfile.query.filter_by(user_id=veteran_id).first()
    if not profile:
        flash('Veteran profile not found.', 'error')
        return redirect(url_for('admin.veteran_management'))

    profile.veteran_tier = tier
    if tier == 'verified':
        profile.is_verified = True
        profile.job_ready_package_active = True
    else:
        profile.is_verified = False
        profile.job_ready_package_active = False

    db.session.commit()
    flash(f'Veteran tier updated to {tier.title()}.', 'success')
    return redirect(url_for('admin.veteran_management'))