import os
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import VeteranProfile, User
from app import db

veteran_bp = Blueprint('veteran', __name__)


# ===============================
# Helpers
# ===============================

def allowed_file(filename, allowed_set=None):
    if not filename:
        return False
    if allowed_set is None:
        allowed_set = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_set


def save_uploaded_file(file, folder_key='UPLOAD_FOLDER', prefix='doc'):
    if file and allowed_file(file.filename):
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"{prefix}_{current_user.id}_{timestamp}{ext}"

        upload_folder = current_app.config[folder_key]
        file_path = os.path.join(upload_folder, unique_filename)
        file.save(file_path)
        return unique_filename
    return None


def save_resume_file(file):
    if file and allowed_file(file.filename, current_app.config['RESUME_EXTENSIONS']):
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(file.filename)
        name, ext = os.path.splitext(filename)
        unique_filename = f"resume_{current_user.id}_{timestamp}{ext}"

        resume_folder = current_app.config['RESUME_FOLDER']
        file_path = os.path.join(resume_folder, unique_filename)
        file.save(file_path)
        return unique_filename
    return None


# ===============================
# Complete Profile
# ===============================

@veteran_bp.route('/profile/complete', methods=['GET', 'POST'])
@login_required
def complete_profile():

    if not current_user.is_veteran():
        flash('Access denied. Veterans only.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':

        profile_type = request.form.get('profile_type', 'veteran')
        is_spouse = profile_type == 'spouse'

        # Common fields
        age = request.form.get('age', '').strip()
        location = request.form.get('location', '').strip()
        bio = request.form.get('bio', '').strip()
        skills = request.form.get('skills', '').strip()
        certifications = request.form.get('certifications', '').strip()
        discharge_type = request.form.get('discharge_type', '').strip()
        deployment_history = request.form.get('deployment_history', '').strip()

        # Veteran fields
        service_branch = request.form.get('service_branch', '').strip()
        rank = request.form.get('rank', '').strip() 
        service_number = request.form.get('service_number', '').strip()
        department = request.form.get('department', '').strip()
        years_of_service = request.form.get('years_of_service', '').strip()

        # Spouse fields
        spouse_branch = request.form.get('spouse_service_branch', '').strip()
        spouse_rank = request.form.get('spouse_rank', '').strip()
        spouse_years = request.form.get('spouse_years_of_service', '').strip()
        relocation_ready = bool(request.form.get('relocation_ready'))
        employment_gap_explanation = request.form.get('employment_gap_explanation', '').strip()

        errors = []

        # Age validation
        try:
            age = int(age)
            if age < 18 or age > 100:
                errors.append('Age must be between 18 and 100.')
        except ValueError:
            errors.append('Age must be a valid number.')

        if not location:
            errors.append('Location is required.')

        # Veteran validation
        if not is_spouse:
            if not all([service_branch, service_number, department, years_of_service]):
                errors.append('All military service fields are required.')

            if service_branch not in ['army', 'navy', 'airforce', 'other']:
                errors.append('Please select a valid service branch.')

            try:
                years_of_service = int(years_of_service)
                if years_of_service < 0 or years_of_service > 50:
                    errors.append('Years of service must be between 0 and 50.')
            except ValueError:
                errors.append('Years of service must be a valid number.')

        # Spouse validation
        if is_spouse:
            if not spouse_branch or not spouse_rank:
                errors.append("Spouse branch and rank are required.")

            try:
                if spouse_years:
                    spouse_years = int(spouse_years)
            except ValueError:
                errors.append("Spouse years of service must be a valid number.")

        # File uploads
        discharge_doc = request.files.get('discharge_document')
        id_doc = request.files.get('id_document')
        resume_file = request.files.get('resume_file')

        if not profile:
            if not discharge_doc or discharge_doc.filename == '':
                errors.append('Discharge document is required.')
            if not id_doc or id_doc.filename == '':
                errors.append('ID document is required.')
            if not resume_file or resume_file.filename == '':
                errors.append('Resume is required.')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('veteran/complete_profile.html', profile=profile)

        try:
            if not profile:
                profile = VeteranProfile(user_id=current_user.id)
                db.session.add(profile)

            profile.age = age
            profile.location = location
            profile.bio = bio
            profile.skills = skills
            profile.certifications = certifications
            profile.discharge_type = discharge_type
            profile.deployment_history = deployment_history
            profile.is_military_spouse = is_spouse

            if not is_spouse:
                profile.service_branch = service_branch
                profile.rank = rank
                profile.service_number = service_number
                profile.department = department
                profile.years_of_service = years_of_service

            if is_spouse:
                profile.spouse_service_branch = spouse_branch
                profile.spouse_rank = spouse_rank
                profile.spouse_years_of_service = spouse_years
                profile.relocation_ready = relocation_ready
                profile.employment_gap_explanation = employment_gap_explanation

            # Save resume
            if resume_file and resume_file.filename != '':
                resume_filename = save_resume_file(resume_file)
                if resume_filename:
                    profile.resume_file = resume_filename
                    profile.resume_last_updated = datetime.utcnow()

            # Save verification docs
            if discharge_doc and discharge_doc.filename != '':
                discharge_filename = save_uploaded_file(discharge_doc, 'UPLOAD_FOLDER', 'discharge')
                if discharge_filename:
                    profile.discharge_document = discharge_filename

            if id_doc and id_doc.filename != '':
                id_filename = save_uploaded_file(id_doc, 'UPLOAD_FOLDER', 'id')
                if id_filename:
                    profile.id_document = id_filename

            profile.verification_status = 'pending'
            profile.updated_at = datetime.utcnow()

            current_user.onboarding_completed = True

            db.session.commit()

            # BREVO UPDATE (SAFE)
            try:
                from services.brevo_service import BrevoService

                BrevoService().update_attributes(
                    current_user,  
                    {
                        "PROFILE_COMPLETED": True,
                        "ONBOARDING_STAGE": "profile_complete",  
                        "USERTYPE": "veteran"  
                    }
                )
            except Exception as e:
                current_app.logger.warning(f"Brevo update failed: {e}")

            flash('Profile submitted successfully. Verification pending.', 'success')
            return redirect(url_for('dashboard.veteran'))

        except Exception:
            db.session.rollback()
            flash('An error occurred while saving your profile.', 'error')
            return render_template('veteran/complete_profile.html', profile=profile)

    return render_template('veteran/complete_profile.html', profile=profile)


# ===============================
# Download Document (SECURE)
# ===============================

@veteran_bp.route('/document/<filename>')
@login_required
def download_document(filename):

    filename = secure_filename(filename)

    if not current_user.is_veteran() and not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.filter_by(user_id=current_user.id).first()

    # Check if profile exists
    if profile is None:
        flash('Profile not found.', 'error')
        return redirect(url_for('dashboard.veteran'))

    if current_user.is_veteran():
        allowed_files = [
            profile.discharge_document,
            profile.id_document
        ]
        if filename not in allowed_files:
            flash('Document not found.', 'error')
            return redirect(url_for('dashboard.veteran'))

    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


# ===============================
# Public Profile
# ===============================

@veteran_bp.route('/profile/<int:user_id>')
@login_required
def public_profile(user_id):
    from models.subscription import Subscription

    # Employers must have Professional or Enterprise Plus to view veteran profiles
    if current_user.is_employer():
        sub = Subscription.query.filter_by(user_id=current_user.id).first()
        has_access = (
            sub
            and sub.status == 'active'
            and sub.expires_at
            and sub.expires_at > datetime.utcnow()
            and sub.plan_type in ('professional', 'enterprise_plus')
        )
        if not has_access:
            flash("Viewing veteran profiles requires a Professional or Enterprise Plus plan.", "warning")
            return redirect(url_for("payments.employer_subscription_plans"))

    user = User.query.get_or_404(user_id)
    profile = user.veteran_profile

    if not profile:
        flash("This veteran's profile is not available.", "warning")
        return redirect(url_for("main.index"))

    return render_template(
        "veteran/public_profile.html",
        user=user,
        profile=profile
    )