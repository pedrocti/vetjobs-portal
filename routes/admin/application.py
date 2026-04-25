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


@admin_bp.route('/applications')
@login_required
def application_monitoring():
    """Admin application monitoring page."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    from models import JobApplication

    # Filter by status if requested
    status_filter = request.args.get('status', '')

    query = JobApplication.query.join(JobPosting, JobApplication.job_id == JobPosting.id).join(User, JobApplication.veteran_id == User.id)

    if status_filter and status_filter in ['pending', 'reviewed', 'accepted', 'rejected']:
        query = query.filter(JobApplication.status == status_filter)

    applications = query.order_by(JobApplication.created_at.desc()).all()

    # Calculate statistics
    stats = {
        'total': JobApplication.query.count(),
        'pending': JobApplication.query.filter_by(status='pending').count(),
        'reviewed': JobApplication.query.filter_by(status='reviewed').count(),
        'accepted': JobApplication.query.filter_by(status='accepted').count(),
        'rejected': JobApplication.query.filter_by(status='rejected').count()
    }

    # Add comprehensive admin stats for sidebar
    admin_stats = get_admin_stats()
    stats.update(admin_stats)

    return render_template('admin/application_monitoring.html', 
                         applications=applications, 
                         stats=stats,
                         current_filter=status_filter)

@admin_bp.route('/applications/<int:application_id>/remove', methods=['POST'])
@login_required
def remove_application(application_id):
    """Remove suspicious application."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    from models import JobApplication
    application = JobApplication.query.get_or_404(application_id)
    admin_reason = request.form.get('admin_reason', '').strip()

    if not admin_reason:
        flash('Please provide a reason for removing this application.', 'error')
        return redirect(url_for('admin.application_monitoring'))

    try:
        # Delete resume file if it exists
        import os
        if application.resume_file:
            resume_path = os.path.join(current_app.config['RESUME_FOLDER'], application.resume_file)
            if os.path.exists(resume_path):
                os.remove(resume_path)

        # Log the removal (in a real system, you might want to keep a log)
        applicant_name = application.veteran.full_name
        job_title = application.job_post.job_title

        db.session.delete(application)
        db.session.commit()

        flash(f'Application by {applicant_name} for "{job_title}" has been removed. Reason: {admin_reason}', 'warning')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while removing the application. Please try again.', 'error')

    return redirect(url_for('admin.application_monitoring'))