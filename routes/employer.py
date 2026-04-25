from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
import os

from app import db
from models import JobPosting, EmployerProfile, Subscription
from utils.security import (
    validate_email,
    validate_phone,
    sanitize_input,
    log_security_event,
    require_completed_profile
)

employer_bp = Blueprint('employer', __name__)


# =========================================================
# SUBSCRIPTION (NEW - SAFE ADDITION)
# =========================================================
from flask import jsonify, request
from models import Subscription


@employer_bp.route('/subscribe/<plan>', methods=['POST'])
@login_required
def subscribe(plan):
    try:
        data = request.get_json() or {}
        billing_cycle = data.get("billing_cycle", "monthly")

        Subscription.create_for_user(
            user=current_user,
            plan_type=plan,
            billing_cycle=billing_cycle
        )

        return jsonify({
            "success": True,
            "message": "Subscription created successfully"
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)

        return jsonify({
            "success": False,
            "message": "Subscription failed"
        }), 500


# =========================================================
# PERMISSION CHECK
# =========================================================
def check_employer_job_permissions():
    if current_user.is_admin():
        return None

    if not current_user.is_employer():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    if current_user.employer_status == 'pending':
        flash('Your account is pending admin approval.', 'warning')
        return redirect(url_for('dashboard.employer'))

    if current_user.employer_status == 'rejected':
        flash('Your account was rejected.', 'error')
        return redirect(url_for('dashboard.employer'))

    subscription = Subscription.get_or_create_for_user(current_user)
    if not subscription or not subscription.is_active():
        flash('Active subscription required to post jobs.', 'warning')
        return redirect(url_for('payments.employer_subscription_plans'))

    if not subscription.can_post_job(current_user.id):
        limit = subscription.max_job_posts
        flash(
            f'You have reached the {limit}-job posting limit on your {subscription.plan_type.replace("_", " ").title()} plan. '
            f'Upgrade to post more jobs.',
            'warning'
        )
        return redirect(url_for('payments.employer_subscription_plans'))

    return None


# =========================================================
# PROFILE COMPLETION
# =========================================================
@employer_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    if not current_user.is_employer():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    profile = EmployerProfile.query.filter_by(user_id=current_user.id).first()

    if not profile:
        profile = EmployerProfile(user_id=current_user.id)
        db.session.add(profile)
        db.session.commit()

    if request.method == 'POST':
        updated = handle_employer_profile_form(profile, is_edit=profile.profile_completed)

        if not updated:
            return render_template('employer/complete_profile.html', profile=profile)

        try:
            db.session.commit()

            profile.profile_completed = True
            profile.profile_completed_at = datetime.utcnow()

            db.session.commit()
            # ✅ BREVO UPDATE (SAFE)
            try:
                from services.brevo_service import BrevoService

                BrevoService().update_attributes(
                    current_user,  
                    {
                        "PROFILE_COMPLETED": True,
                        "ONBOARDING_STAGE": "profile_complete",  
                        "USERTYPE": "employer"  
                    }
                )
            except Exception as e:
                current_app.logger.warning(f"Brevo update failed: {e}")

            flash('Profile saved successfully.', 'success')
            return redirect(url_for('dashboard.employer'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(e)
            flash('Error saving profile.', 'error')

    return render_template('employer/complete_profile.html', profile=profile)


# =========================================================
# PROFILE HANDLER (SAFE)
# =========================================================
def handle_employer_profile_form(profile, is_edit=False):
    errors = []

    company_name = sanitize_input(request.form.get('company_name', ''), 200)
    industry = sanitize_input(request.form.get('industry', ''), 100)
    recruiter_name = sanitize_input(request.form.get('recruiter_name', ''), 100)
    recruiter_position = sanitize_input(request.form.get('recruiter_position', ''), 100)
    recruiter_email = sanitize_input(request.form.get('recruiter_email', ''), 120).lower()
    recruiter_phone = sanitize_input(request.form.get('recruiter_phone', ''), 20)
    company_logo = sanitize_input(request.form.get('company_logo', ''), 255)

    if not is_edit:
        if not company_name:
            errors.append("Company name required")
        if not industry:
            errors.append("Industry required")

    if recruiter_email and not validate_email(recruiter_email):
        errors.append("Invalid email")

    if recruiter_phone and not validate_phone(recruiter_phone):
        errors.append("Invalid phone")

    if errors:
        for e in errors:
            flash(e, 'error')
        return None

    profile.company_name = company_name
    profile.industry = industry
    profile.company_logo = company_logo
    profile.recruiter_name = recruiter_name
    profile.recruiter_position = recruiter_position
    profile.recruiter_email = recruiter_email
    profile.recruiter_phone = recruiter_phone
    profile.updated_at = datetime.utcnow()

    return profile


# =========================================================
# POST JOB
# =========================================================
@employer_bp.route('/post-job', methods=['GET', 'POST'])
@login_required
def post_job():

    if not current_user.is_employer() and not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    if not current_user.is_admin():
        check = check_employer_job_permissions()
        if check:
            return check
        subscription = Subscription.get_or_create_for_user(current_user)
    else:
        subscription = None

    if request.method == 'POST':
        title = sanitize_input(request.form.get('job_title', ''), 200)
        company = sanitize_input(request.form.get('company_name', ''), 200)
        location = sanitize_input(request.form.get('location', ''), 200)
        job_type = sanitize_input(request.form.get('job_type', ''), 50)
        description = sanitize_input(request.form.get('job_description', ''), 5000)
        requirements = sanitize_input(request.form.get('requirements', ''), 5000)

        if not all([title, company, location, job_type, description]):
            flash("All fields required", "error")
            return render_template("employer/post_job.html")

        job = JobPosting(
            posted_by=current_user.id,
            title=title,
            company_name=company,
            location=location,
            job_type=job_type,
            description=description,
            requirements=requirements,
            status='approved' if current_user.is_admin() else 'pending',
            is_active=True,
            is_featured=getattr(subscription, 'featured_jobs', False),
            promote_on_social=getattr(subscription, 'social_promotion', False)
        )

        try:
            profile = EmployerProfile.query.filter_by(user_id=current_user.id).first()
            job.company_logo = profile.company_logo if profile and profile.company_logo else "images/vetjoblogo1.png"

            db.session.add(job)
            db.session.commit()

            flash("Job posted successfully", "success")
            return redirect(url_for('employer.manage_jobs'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(e)
            flash("Error posting job", "error")

    return render_template("employer/post_job.html")


# =========================================================
# MANAGE JOBS
# =========================================================
@employer_bp.route('/manage-jobs')
@login_required
@require_completed_profile
def manage_jobs():

    if current_user.is_admin():
        jobs = JobPosting.query.order_by(JobPosting.created_at.desc()).all()
    elif current_user.is_employer():
        jobs = JobPosting.query.filter_by(
            posted_by=current_user.id
        ).order_by(JobPosting.created_at.desc()).all()
    else:
        flash("Access denied", "error")
        return redirect(url_for('main.index'))

    stats = {
        "total": len(jobs),
        "active": len([j for j in jobs if j.is_active]),
        "pending": len([j for j in jobs if j.status == "pending"]),
        "rejected": len([j for j in jobs if j.status == "rejected"])
    }

    return render_template("employer/manage_jobs.html", job_posts=jobs, stats=stats)


# =========================================================
# EDIT JOB
# =========================================================
@employer_bp.route('/edit_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):

    job = JobPosting.query.get_or_404(job_id)

    if not current_user.is_admin() and job.posted_by != current_user.id:
        flash("Not allowed", "error")
        return redirect(url_for('employer.manage_jobs'))

    if request.method == "POST":
        job.title = request.form.get("title", "").strip()
        job.company_name = request.form.get("company_name", "").strip()
        job.location = request.form.get("location", "").strip()
        job.job_type = request.form.get("job_type", "").strip()
        job.description = request.form.get("description", "").strip()
        job.requirements = request.form.get("requirements", "").strip()

        db.session.commit()
        flash("Updated successfully", "success")
        return redirect(url_for('employer.manage_jobs'))

    return render_template("employer/edit_job.html", job_post=job)


# =========================================================
# DELETE JOB
# =========================================================
@employer_bp.route('/delete-job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):

    job = JobPosting.query.get_or_404(job_id)

    if not current_user.is_admin() and job.posted_by != current_user.id:
        flash("Not allowed", "error")
        return redirect(url_for('employer.manage_jobs'))

    db.session.delete(job)
    db.session.commit()

    flash("Job deleted", "success")
    return redirect(url_for('employer.manage_jobs'))


# =========================================================
# TOGGLE JOB
# =========================================================
@employer_bp.route('/toggle-job/<int:job_id>', methods=['POST'])
@login_required
def toggle_job_status(job_id):

    job = JobPosting.query.get_or_404(job_id)

    if not current_user.is_admin() and job.posted_by != current_user.id:
        flash("Not allowed", "error")
        return redirect(url_for('employer.manage_jobs'))

    job.is_active = not job.is_active
    job.updated_at = datetime.utcnow()

    db.session.commit()
    flash("Job status updated", "success")

    return redirect(url_for('employer.manage_jobs'))


# =========================================================
# VIEW JOB
# =========================================================
@employer_bp.route('/job/<int:job_id>')
@login_required
def view_job(job_id):

    job = JobPosting.query.get_or_404(job_id)

    if not current_user.is_admin() and job.posted_by != current_user.id:
        flash("Not allowed", "error")
        return redirect(url_for('employer.manage_jobs'))

    return render_template("employer/view_job.html", job_post=job)