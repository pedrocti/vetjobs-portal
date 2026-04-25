import os
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_from_directory, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import JobApplication, JobPosting, VeteranProfile, User, Subscription
from app import db
from services.notification_service import notification_service
from datetime import datetime

applications_bp = Blueprint('applications', __name__)


def allowed_resume_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['RESUME_EXTENSIONS']


def save_resume_file(file, prefix='resume'):
    if file and allowed_resume_file(file.filename):

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)

        unique_filename = f"{prefix}_{current_user.id}_{timestamp}_{name}{ext}"

        upload_dir = os.path.join(
            current_app.root_path,
            'static',
            'uploads',
            'resumes'
        )

        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, unique_filename)
        file.save(file_path)

        return unique_filename

    return None


@applications_bp.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply_to_job(job_id):
    if not current_user.is_authenticated:
        flash('Please create an account or log in to apply for jobs.', 'info')
        return redirect(url_for('auth.login', next=request.url))

    return authenticated_apply_to_job(job_id)


@applications_bp.route('/authenticated-apply/<int:job_id>', methods=['GET', 'POST'])
@login_required
def authenticated_apply_to_job(job_id):

    if not current_user.is_veteran():
        flash('Access denied. Veterans only.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.is_verified or profile.verification_status != 'approved':
        flash('You must complete and verify your veteran profile to apply for jobs.', 'warning')
        return redirect(url_for('dashboard.veteran'))

    job_post = JobPosting.query.get_or_404(job_id)

    if job_post.status != 'approved' or not job_post.is_active:
        flash('This job is no longer accepting applications.', 'error')
        return redirect(url_for('jobs.job_board'))

    existing_application = JobApplication.query.filter_by(
        job_id=job_id,
        veteran_id=current_user.id
    ).first()

    if existing_application:
        flash('You have already applied to this job.', 'warning')
        return redirect(url_for('applications.my_applications'))

    if request.method == 'POST':
        cover_letter = request.form.get('cover_letter', '').strip()
        resume_file = request.files.get('resume_file')

        errors = []

        if not cover_letter:
            errors.append('Cover letter is required.')

        if len(cover_letter) < 50:
            errors.append('Cover letter must be at least 50 characters long.')

        if not resume_file or resume_file.filename == '':
            errors.append('Resume file is required.')
        elif not allowed_resume_file(resume_file.filename):
            errors.append('Invalid resume file type.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('applications/apply.html', job_post=job_post)

        try:
            resume_filename = save_resume_file(resume_file, 'resume')

            if not resume_filename:
                flash('Error uploading resume file.', 'error')
                return render_template('applications/apply.html', job_post=job_post)

            application = JobApplication(
                job_id=job_id,
                veteran_id=current_user.id,
                cover_letter=cover_letter,
                resume_file=resume_filename,
                status='pending'
            )

            db.session.add(application)
            db.session.commit()

            employer = User.query.get(job_post.posted_by)
            if employer:
                notification_service.notify_application_received(
                    employer_id=employer.id,
                    veteran_name=current_user.full_name,
                    job_title=job_post.title,
                    application_id=application.id
                )

            flash('Application submitted successfully!', 'success')
            return redirect(url_for('applications.my_applications'))

        except Exception:
            db.session.rollback()
            flash('An error occurred while submitting your application.', 'error')

    return render_template('applications/apply.html', job_post=job_post)


@applications_bp.route('/my-applications')
@login_required
def my_applications():

    if not current_user.is_veteran():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    applications = JobApplication.query.filter_by(
        veteran_id=current_user.id
    ).order_by(JobApplication.created_at.desc()).all()

    stats = {
        'total': len(applications),
        'pending': len([a for a in applications if a.status == 'pending']),
        'reviewed': len([a for a in applications if a.status == 'reviewed']),
        'accepted': len([a for a in applications if a.status == 'accepted']),
        'rejected': len([a for a in applications if a.status == 'rejected'])
    }

    return render_template('applications/my_applications.html', applications=applications, stats=stats)


@applications_bp.route('/withdraw/<int:application_id>', methods=['POST'])
@login_required
def withdraw_application(application_id):

    if not current_user.is_veteran():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    application = JobApplication.query.get_or_404(application_id)

    if application.veteran_id != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('applications.my_applications'))

    if application.status in ['accepted', 'rejected']:
        flash('Cannot withdraw processed application.', 'error')
        return redirect(url_for('applications.my_applications'))

    try:
        if application.resume_file:
            path = os.path.join(
                current_app.root_path,
                'static',
                'uploads',
                'resumes',
                application.resume_file
            )
            if os.path.exists(path):
                os.remove(path)

        db.session.delete(application)
        db.session.commit()

        flash('Application withdrawn.', 'success')

    except Exception:
        db.session.rollback()
        flash('Error withdrawing application.', 'error')

    return redirect(url_for('applications.my_applications'))


@applications_bp.route('/resume/<int:application_id>')
@login_required
def download_resume(application_id):

    application = JobApplication.query.get_or_404(application_id)

    upload_folder = os.path.join(
        current_app.root_path,
        'static',
        'uploads',
        'resumes'
    )

    filename = application.resume_file
    if not filename:
        abort(404)

    # ADMIN
    if current_user.is_admin():
        pass

    # EMPLOYER
    elif current_user.is_employer():

        if application.job_post.posted_by != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('applications.manage_applications'))

        subscription = Subscription.query.filter_by(
            user_id=current_user.id,
            status='active'
        ).first()

        if not subscription or subscription.plan_type not in ['starter', 'professional', 'enterprise']:
            flash('Upgrade your plan to access resumes.', 'warning')
            return redirect(url_for('payments.employer_subscription_plans'))

    # VETERAN
    elif current_user.is_veteran():

        if application.veteran_id != current_user.id:
            flash('Access denied.', 'error')
            return redirect(url_for('applications.my_applications'))

    else:
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    try:
        file_path = os.path.join(upload_folder, filename)

        if not os.path.exists(file_path):
            abort(404)

        return send_from_directory(
            upload_folder,
            filename,
            as_attachment=True
        )

    except Exception:
        abort(500)


@applications_bp.route('/manage')
@login_required
def manage_applications():

    if not current_user.is_employer():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    subscription = Subscription.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).first()

    job_posts = JobPosting.query.filter_by(
        posted_by=current_user.id
    ).order_by(JobPosting.created_at.desc()).all()

    applications = JobApplication.query.join(JobPosting)\
        .filter(JobPosting.posted_by == current_user.id)\
        .order_by(JobApplication.created_at.desc()).all()

    total_applications = len(applications)
    pending_applications = len([a for a in applications if a.status == 'pending'])

    return render_template(
        'applications/manage_applications.html',
        job_posts=job_posts,
        applications=applications,
        total_applications=total_applications,
        pending_applications=pending_applications,
        subscription=subscription
    )


@applications_bp.route('/review/<int:application_id>')
@login_required
def review_application(application_id):

    if not current_user.is_employer():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    application = JobApplication.query.get_or_404(application_id)

    if application.job_post.posted_by != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('applications.manage_applications'))

    subscription = Subscription.query.filter_by(
        user_id=current_user.id,
        status='active'
    ).first()

    return render_template(
        'applications/review_application.html',
        application=application,
        subscription=subscription
    )


@applications_bp.route('/update-status/<int:application_id>', methods=['POST'])
@login_required
def update_application_status(application_id):

    if not current_user.is_employer():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    application = JobApplication.query.get_or_404(application_id)

    if application.job_post.posted_by != current_user.id:
        flash('Access denied.', 'error')
        return redirect(url_for('applications.manage_applications'))

    new_status = request.form.get('status')
    employer_notes = request.form.get('employer_notes', '').strip()

    if new_status not in ['pending', 'reviewed', 'accepted', 'rejected']:
        flash('Invalid status.', 'error')
        return redirect(url_for('applications.review_application', application_id=application_id))

    try:
        old_status = application.status

        application.status = new_status
        application.employer_notes = employer_notes
        application.reviewed_by = current_user.id
        application.reviewed_at = datetime.utcnow()
        application.updated_at = datetime.utcnow()

        db.session.commit()

        if old_status != new_status:
            veteran = User.query.get(application.veteran_id)
            if veteran:
                notification_service.notify_application_status_change(
                    user_id=veteran.id,
                    job_title=application.job_post.title,
                    status=new_status,
                    employer_message=employer_notes
                )

        flash('Application updated.', 'success')

    except Exception:
        db.session.rollback()
        flash('Error updating application.', 'error')

    return redirect(url_for('applications.manage_applications'))