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


@admin_bp.route('/jobs')
@login_required
def job_moderation():
    """Admin job moderation page."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Get all job posts that need moderation
    pending_jobs = JobPosting.query.filter_by(status='pending').all()
    approved_jobs = JobPosting.query.filter_by(status='approved').all()
    rejected_jobs = JobPosting.query.filter_by(status='rejected').all()
    flagged_jobs = JobPosting.query.filter_by(status='flagged').all()

    # Get comprehensive admin stats
    stats = get_admin_stats()

    return render_template('admin/job_moderation.html', 
                         pending_jobs=pending_jobs,
                         approved_jobs=approved_jobs,
                         rejected_jobs=rejected_jobs,
                         flagged_jobs=flagged_jobs,
                         stats=stats)

@admin_bp.route('/job/<int:job_id>')
@login_required
def review_job(job_id):
    """Review a specific job posting."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job_post = JobPosting.query.get_or_404(job_id)
    return render_template('admin/review_job.html', job_post=job_post)

@admin_bp.route('/job/<int:job_id>/approve', methods=['POST'])
@login_required
def approve_job(job_id):
    """Approve a job posting."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job_post = JobPosting.query.get_or_404(job_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    try:
        job_post.status = 'approved'
        job_post.is_active = True  
        job_post.moderated_by = current_user.id
        job_post.moderated_at = datetime.utcnow()
        job_post.admin_notes = admin_notes
        job_post.updated_at = datetime.utcnow()

        db.session.commit()
        flash(f'✅ Job "{job_post.job_title}" has been approved successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'⚠️ Error approving job: {str(e)}', 'error')

    return redirect(url_for('admin.job_moderation'))


@admin_bp.route('/job/<int:job_id>/reject', methods=['POST'])
@login_required
def reject_job(job_id):
    """Reject a job posting."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job_post = JobPosting.query.get_or_404(job_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    if not admin_notes:
        flash('Please provide a reason for rejection.', 'error')
        return redirect(url_for('admin.review_job', job_id=job_id))

    try:
        job_post.status = 'rejected'
        job_post.is_active = False
        job_post.moderated_by = current_user.id
        job_post.moderated_at = datetime.utcnow()
        job_post.admin_notes = admin_notes
        job_post.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Job "{job_post.job_title}" has been rejected.', 'warning')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while rejecting the job. Please try again.', 'error')

    return redirect(url_for('admin.job_moderation'))

@admin_bp.route('/job/<int:job_id>/flag', methods=['POST'])
@login_required
def flag_job(job_id):
    """Flag a job posting for review."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job_post = JobPosting.query.get_or_404(job_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    if not admin_notes:
        flash('Please provide a reason for flagging.', 'error')
        return redirect(url_for('admin.review_job', job_id=job_id))

    try:
        job_post.status = 'flagged'
        job_post.is_active = False
        job_post.moderated_by = current_user.id
        job_post.moderated_at = datetime.utcnow()
        job_post.admin_notes = admin_notes
        job_post.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Job "{job_post.job_title}" has been flagged for review.', 'info')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while flagging the job. Please try again.', 'error')

    return redirect(url_for('admin.job_moderation'))