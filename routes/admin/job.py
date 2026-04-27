from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, case
from datetime import datetime, timedelta, date
import os
from . import admin_bp

from .stats import get_admin_stats
from app import db
from models import (
    User, VeteranProfile, EmployerProfile, Partner,
    JobPosting, JobApplication, Payment, Subscription,
    PaymentSetting, EmailSetting, Message, Testimonial
)

# ── Allowed image extensions for logo upload ──
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_logo(file):
    """Save uploaded logo file and return the relative path, or None on failure."""
    if not file or file.filename == '':
        return None
    if not allowed_file(file.filename):
        return None
    filename = secure_filename(file.filename)
    # Prefix with timestamp to avoid collisions
    filename = f"job_logo_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'job_logos')
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))
    return f"uploads/job_logos/{filename}"


# ─────────────────────────────────────────────
#  EXISTING: Job moderation list
# ─────────────────────────────────────────────
@admin_bp.route('/jobs')
@login_required
def job_moderation():
    """Admin job moderation page."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    pending_jobs = JobPosting.query.filter_by(status='pending').all()
    approved_jobs = JobPosting.query.filter_by(status='approved').all()
    rejected_jobs = JobPosting.query.filter_by(status='rejected').all()
    flagged_jobs = JobPosting.query.filter_by(status='flagged').all()
    stats = get_admin_stats()

    from datetime import date
    return render_template('admin/job_moderation.html',
                           pending_jobs=pending_jobs,
                           approved_jobs=approved_jobs,
                           rejected_jobs=rejected_jobs,
                           flagged_jobs=flagged_jobs,
                           stats=stats,
                           today=date.today())


# ─────────────────────────────────────────────
#  EXISTING: Review a job
# ─────────────────────────────────────────────
@admin_bp.route('/job/<int:job_id>')
@login_required
def review_job(job_id):
    """Review a specific job posting."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job_post = JobPosting.query.get_or_404(job_id)
    return render_template('admin/review_job.html', job_post=job_post)


# ─────────────────────────────────────────────
#  NEW: Admin post a job
# ─────────────────────────────────────────────
@admin_bp.route('/jobs/post', methods=['GET', 'POST'])
@login_required
def post_job():
    """Admin posts a job directly — goes live immediately."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        try:
            # ── Core fields ──
            title = request.form.get('job_title', '').strip()
            company_name = request.form.get('company_name', '').strip()
            location = request.form.get('location', '').strip()
            job_type = request.form.get('job_type', 'full-time')
            description = request.form.get('job_description', '').strip()
            requirements = request.form.get('requirements', '').strip()
            benefits = request.form.get('benefits', '').strip()
            industry = request.form.get('industry', '').strip()
            experience_level = request.form.get('experience_level', '').strip()

            # ── Salary ──
            salary_min = request.form.get('salary_min', '').strip()
            salary_max = request.form.get('salary_max', '').strip()
            salary_min = int(salary_min) if salary_min.isdigit() else None
            salary_max = int(salary_max) if salary_max.isdigit() else None

            # ── Admin-only fields ──
            external_apply_url = request.form.get('external_apply_url', '').strip() or None
            deadline_str = request.form.get('deadline', '').strip()
            deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

            # ── Logo upload ──
            logo_path = None
            if 'company_logo' in request.files:
                logo_path = _save_logo(request.files['company_logo'])

            # ── Validation ──
            if not title or not company_name or not location or not description or not requirements:
                flash('Please fill in all required fields.', 'error')
                return render_template('admin/post_job.html')

            # ── Create job — admin posts go live immediately ──
            job = JobPosting(
                title=title,
                company_name=company_name,
                location=location,
                job_type=job_type,
                description=description,
                requirements=requirements,
                benefits=benefits or None,
                industry=industry or None,
                experience_level=experience_level or None,
                salary_min=salary_min,
                salary_max=salary_max,
                external_apply_url=external_apply_url,
                deadline=deadline,
                company_logo=logo_path,
                posted_by=current_user.id,
                status='approved',      # Admin posts go live immediately
                is_active=True,
                moderated_by=current_user.id,
                moderated_at=datetime.utcnow(),
            )

            db.session.add(job)
            db.session.commit()
            flash(f'✅ Job "{title}" posted and live immediately.', 'success')
            return redirect(url_for('admin.job_moderation'))

        except Exception as e:
            db.session.rollback()
            flash(f'⚠️ Error posting job: {str(e)}', 'error')

    return render_template('admin/post_job.html')


# ─────────────────────────────────────────────
#  NEW: Admin edit any job
# ─────────────────────────────────────────────
@admin_bp.route('/job/<int:job_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    """Admin can edit any job posting."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job = JobPosting.query.get_or_404(job_id)

    if request.method == 'POST':
        try:
            job.title = request.form.get('job_title', '').strip()
            job.company_name = request.form.get('company_name', '').strip()
            job.location = request.form.get('location', '').strip()
            job.job_type = request.form.get('job_type', 'full-time')
            job.description = request.form.get('job_description', '').strip()
            job.requirements = request.form.get('requirements', '').strip()
            job.benefits = request.form.get('benefits', '').strip() or None
            job.industry = request.form.get('industry', '').strip() or None
            job.experience_level = request.form.get('experience_level', '').strip() or None

            salary_min = request.form.get('salary_min', '').strip()
            salary_max = request.form.get('salary_max', '').strip()
            job.salary_min = int(salary_min) if salary_min.isdigit() else None
            job.salary_max = int(salary_max) if salary_max.isdigit() else None

            job.external_apply_url = request.form.get('external_apply_url', '').strip() or None

            deadline_str = request.form.get('deadline', '').strip()
            job.deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

            job.status = request.form.get('status', job.status)
            job.is_active = request.form.get('is_active') == 'on'
            job.updated_at = datetime.utcnow()

            # ── Logo upload (only replaces if a new file is uploaded) ──
            if 'company_logo' in request.files:
                new_logo = _save_logo(request.files['company_logo'])
                if new_logo:
                    job.company_logo = new_logo

            # ── Allow clearing the logo ──
            if request.form.get('clear_logo') == 'yes':
                job.company_logo = None

            if not job.title or not job.company_name or not job.location:
                flash('Job title, company name, and location are required.', 'error')
                return render_template('admin/edit_job.html', job=job)

            db.session.commit()
            flash(f'✅ Job "{job.title}" updated successfully.', 'success')
            return redirect(url_for('admin.review_job', job_id=job.id))

        except Exception as e:
            db.session.rollback()
            flash(f'⚠️ Error updating job: {str(e)}', 'error')

    return render_template('admin/edit_job.html', job=job)


# ─────────────────────────────────────────────
#  NEW: Admin delete any job
# ─────────────────────────────────────────────
@admin_bp.route('/job/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    """Admin can delete any job posting."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    job = JobPosting.query.get_or_404(job_id)
    title = job.title

    try:
        # Delete associated applications first to avoid FK constraint errors
        JobApplication.query.filter_by(job_id=job.id).delete()
        db.session.delete(job)
        db.session.commit()
        flash(f'🗑️ Job "{title}" has been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'⚠️ Error deleting job: {str(e)}', 'error')

    return redirect(url_for('admin.job_moderation'))


# ─────────────────────────────────────────────
#  EXISTING: Approve / Reject / Flag
# ─────────────────────────────────────────────
@admin_bp.route('/job/<int:job_id>/approve', methods=['POST'])
@login_required
def approve_job(job_id):
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
