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
    page = request.args.get('page', 1, type=int)
    per_page = 20

    pending_pagination = (
        JobPosting.query
        .filter_by(status='pending')
        .order_by(JobPosting.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    approved_jobs = (
        JobPosting.query
        .filter_by(status='approved')
        .order_by(JobPosting.created_at.desc())
        
        .all()
    )

    rejected_jobs = (
        JobPosting.query
        .filter_by(status='rejected')
        .order_by(JobPosting.created_at.desc())
        .limit(5)
        .all()
    )

    flagged_jobs = (
        JobPosting.query
        .filter_by(status='flagged')
        .order_by(JobPosting.created_at.desc())
        .all()
    )

    return render_template(
        'admin/job_moderation.html',
        pending_jobs=pending_pagination.items,
        pending_pagination=pending_pagination,
        approved_jobs=approved_jobs,
        rejected_jobs=rejected_jobs,
        flagged_jobs=flagged_jobs
    )


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

@admin_bp.route('/job/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    from .stats import get_admin_stats
    from werkzeug.utils import secure_filename
    import os

    job   = JobPosting.query.get_or_404(job_id)
    stats = get_admin_stats()

    if request.method == 'POST':
        try:
            job.title            = request.form.get('job_title', '').strip()
            job.company_name     = request.form.get('company_name', '').strip()
            job.location         = request.form.get('location', '').strip()
            job.job_type         = request.form.get('job_type', 'full-time')
            job.industry         = request.form.get('industry', '').strip() or None
            job.experience_level = request.form.get('experience_level', '').strip() or None
            job.description      = request.form.get('job_description', '').strip()
            job.requirements     = request.form.get('requirements', '').strip()
            job.status           = request.form.get('status', job.status)
            job.is_active        = bool(request.form.get('is_active'))
            job.updated_at       = datetime.utcnow()

            sal_min = request.form.get('salary_min', '').strip()
            sal_max = request.form.get('salary_max', '').strip()
            job.salary_min = int(sal_min) if sal_min.isdigit() else None
            job.salary_max = int(sal_max) if sal_max.isdigit() else None

            logo_file = request.files.get('company_logo')
            if request.form.get('clear_logo') == 'yes':
                job.company_logo = 'images/vetjoblogo1.png'
            elif logo_file and logo_file.filename:
                from werkzeug.utils import secure_filename
                filename  = secure_filename(logo_file.filename)
                ext       = os.path.splitext(filename)[1]
                unique    = f"job_logo_{job.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique)
                logo_file.save(save_path)
                job.company_logo = f"uploads/{unique}"

            try:
                job.external_apply_url = request.form.get('external_apply_url', '').strip() or None
            except Exception:
                pass

            try:
                deadline_str = request.form.get('deadline', '').strip()
                job.deadline = datetime.strptime(deadline_str, '%Y-%m-%d') if deadline_str else None
            except Exception:
                pass

            db.session.commit()
            flash(f'✅ "{job.title}" updated successfully.', 'success')
            return redirect(url_for('admin.review_job', job_id=job.id))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'[admin.edit_job] {e}', exc_info=True)
            flash(f'Error saving changes: {e}', 'error')

    return render_template('admin/edit_job.html', job=job, stats=stats)


@admin_bp.route('/job/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    job   = JobPosting.query.get_or_404(job_id)
    title = job.title

    try:
        JobApplication.query.filter_by(job_id=job.id).delete()
        db.session.delete(job)
        db.session.commit()
        flash(f'🗑️ "{title}" and all its applications deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'[admin.delete_job] {e}', exc_info=True)
        flash(f'Error deleting job: {e}', 'error')

    return redirect(url_for('admin.job_moderation'))


@admin_bp.route('/job/<int:job_id>/toggle', methods=['POST'])
@login_required
def toggle_job(job_id):
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    job            = JobPosting.query.get_or_404(job_id)
    job.is_active  = not job.is_active
    job.updated_at = datetime.utcnow()
    db.session.commit()

    state = 'activated' if job.is_active else 'deactivated'
    flash(f'"{job.title}" {state}.', 'info')
    return redirect(request.referrer or url_for('admin.job_moderation'))
