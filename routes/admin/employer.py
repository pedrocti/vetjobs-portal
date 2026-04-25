from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, case
from datetime import datetime, timedelta
import os
from decimal import Decimal
from . import admin_bp

# Import shared database and models
from app import db
from .stats import get_admin_stats
from models import (
    User, VeteranProfile, EmployerProfile, Partner,
    JobPosting, JobApplication, Payment, Subscription,
    PaymentSetting, EmailSetting, Message, Testimonial
)

@admin_bp.route('/employers')
@login_required
def employer_management():
    """Comprehensive employer management interface."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Get filter parameters
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '')

    # Base query
    query = User.query.filter_by(user_type='employer')

    # Apply filters
    if search:
        query = query.filter(or_(
            User.full_name.ilike(f'%{search}%'),
            User.email.ilike(f'%{search}%'),
            User.username.ilike(f'%{search}%')
        ))

    if status_filter == 'active':
        query = query.filter(User.employer_status == 'active')
    elif status_filter == 'pending':
        query = query.filter(User.employer_status == 'pending')
    elif status_filter == 'rejected':
        query = query.filter(User.employer_status == 'rejected')

    employers = query.order_by(desc(User.created_at)).all()

    # Optimize by eager loading employer profiles and computing job counts in bulk
    employer_ids = [employer.id for employer in employers]

    # Fetch job counts in bulk to avoid N+1 queries
    job_counts = db.session.query(
        JobPosting.posted_by,
        func.count(JobPosting.id).label('total_jobs'),
        func.sum(case((JobPosting.is_active == True, 1), else_=0)).label('active_jobs')
    ).filter(JobPosting.posted_by.in_(employer_ids)).group_by(JobPosting.posted_by).all()


    # Convert to dictionaries for easy lookup
    job_count_dict = {
        jc.posted_by: {
            'total': int(jc.total_jobs),
            'active': int(jc.active_jobs or 0)
        } 
        for jc in job_counts
    }


    # Fetch employer profiles in bulk
    profiles = EmployerProfile.query.filter(EmployerProfile.user_id.in_(employer_ids)).all()
    profile_dict = {profile.user_id: profile for profile in profiles}

    # Attach data to employer objects
    for employer in employers:
        job_data = job_count_dict.get(employer.id, {'total': 0, 'active': 0})
        employer.job_count = job_data['total']
        employer.active_job_count = job_data['active']
        employer.profile_data = profile_dict.get(employer.id)

    # Calculate stats
    stats = {
        'total': User.query.filter_by(user_type='employer').count(),
        'active': User.query.filter_by(user_type='employer', employer_status='active').count(),
        'pending': User.query.filter_by(user_type='employer', employer_status='pending').count(),
        'rejected': User.query.filter_by(user_type='employer', employer_status='rejected').count(),
        'with_jobs': db.session.query(User).join(JobPosting, User.id == JobPosting.posted_by).filter(User.user_type == 'employer').distinct().count()
    }

    # Add comprehensive admin stats for sidebar
    admin_stats = get_admin_stats()
    stats.update(admin_stats)

    return render_template('admin/employer_management.html', 
                         employers=employers, 
                         stats=stats,
                         current_filters={
                             'search': search,
                             'status': status_filter
                         })

@admin_bp.route('/employer/<int:employer_id>/approve', methods=['POST'])
@login_required
def approve_employer(employer_id):
    """Approve an employer account."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    employer = User.query.get_or_404(employer_id)

    if not employer.is_employer():
        flash('User is not an employer.', 'error')
        return redirect(url_for('admin.employer_management'))

    if employer.approve_employer():
        db.session.commit()
        flash(f'Employer {employer.full_name} has been approved successfully.', 'success')

        # TODO: Send approval email notification here
        # send_employer_approval_email(employer)

    else:
        flash('Failed to approve employer.', 'error')

    return redirect(url_for('admin.employer_management'))

@admin_bp.route('/employer/<int:employer_id>/reject', methods=['POST'])
@login_required
def reject_employer(employer_id):
    """Reject an employer account."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    employer = User.query.get_or_404(employer_id)

    if not employer.is_employer():
        flash('User is not an employer.', 'error')
        return redirect(url_for('admin.employer_management'))

    rejection_reason = request.form.get('rejection_reason', 'No reason provided')

    if employer.reject_employer():
        db.session.commit()
        flash(f'Employer {employer.full_name} has been rejected.', 'warning')

        # TODO: Send rejection email notification here
        # send_employer_rejection_email(employer, rejection_reason)

    else:
        flash('Failed to reject employer.', 'error')

    return redirect(url_for('admin.employer_management'))

@admin_bp.route('/user/<int:user_id>/toggle-status', methods=['POST'])
@login_required
def toggle_user_status(user_id):
    """Toggle user active/inactive status."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    user = User.query.get_or_404(user_id)
    admin_reason = request.form.get('admin_reason', '').strip()

    if not admin_reason:
        flash('Please provide a reason for status change.', 'error')
        return redirect(request.referrer or url_for('admin.dashboard'))

    try:
        new_status = not user.active
        user.active = new_status
        user.updated_at = datetime.utcnow()

        # Log the action (in production, you'd want a proper audit log)
        action = 'activated' if new_status else 'suspended'

        db.session.commit()

        flash(f'User {user.full_name} has been {action}. Reason: {admin_reason}', 'success')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating user status. Please try again.', 'error')

    return redirect(request.referrer or url_for('admin.dashboard'))