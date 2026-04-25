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


@admin_bp.route('/verifications')
@login_required
def verification_management():
    """Admin verification management page."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # Get all veteran profiles that need verification
    pending_veteran_profiles = VeteranProfile.query.filter_by(verification_status='pending').all()
    approved_veteran_profiles = VeteranProfile.query.filter_by(verification_status='approved').all()
    rejected_veteran_profiles = VeteranProfile.query.filter_by(verification_status='rejected').all()

    # Get all employer profiles that need verification
    from models import EmployerProfile
    pending_employer_profiles = EmployerProfile.query.filter_by(verification_status='pending').all()
    approved_employer_profiles = EmployerProfile.query.filter_by(verification_status='approved').all()
    rejected_employer_profiles = EmployerProfile.query.filter_by(verification_status='rejected').all()

    # Get comprehensive admin stats
    stats = get_admin_stats()

    return render_template(
        'admin/verification.html',
        pending_profiles=pending_veteran_profiles,
        approved_profiles=approved_veteran_profiles,
        rejected_profiles=rejected_veteran_profiles,

        pending_employer_profiles=pending_employer_profiles,
        approved_employer_profiles=approved_employer_profiles,
        rejected_employer_profiles=rejected_employer_profiles,

        stats=stats
    )

@admin_bp.route('/verification/<int:profile_id>')
@login_required
def review_profile(profile_id):
    """Review a specific veteran profile."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.get_or_404(profile_id)
    return render_template('admin/review_profile.html', profile=profile)

@admin_bp.route('/verification/<int:profile_id>/approve', methods=['POST'])
@login_required
def approve_profile(profile_id):
    """Approve a veteran profile."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.get_or_404(profile_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    try:
        profile.verification_status = 'approved'
        profile.is_verified = True
        profile.verified_by = current_user.id
        profile.verified_at = datetime.utcnow()
        profile.admin_notes = admin_notes
        profile.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Profile for {profile.user.full_name} has been approved successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while approving the profile. Please try again.', 'error')

    return redirect(url_for('admin.verification_management'))

@admin_bp.route('/verification/<int:profile_id>/reject', methods=['POST'])
@login_required
def reject_profile(profile_id):
    """Reject a veteran profile."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.get_or_404(profile_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    if not admin_notes:
        flash('Please provide a reason for rejection.', 'error')
        return redirect(url_for('admin.review_profile', profile_id=profile_id))

    try:
        profile.verification_status = 'rejected'
        profile.is_verified = False
        profile.verified_by = current_user.id
        profile.verified_at = datetime.utcnow()
        profile.admin_notes = admin_notes
        profile.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Profile for {profile.user.full_name} has been rejected.', 'warning')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while rejecting the profile. Please try again.', 'error')

    return redirect(url_for('admin.verification_management'))

# Employer Profile Verification Routes
@admin_bp.route('/employer-verification/<int:profile_id>')
@login_required
def review_employer_profile(profile_id):
    """Review a specific employer profile."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    from models import EmployerProfile
    profile = EmployerProfile.query.get_or_404(profile_id)
    return render_template('admin/review_employer_profile.html', profile=profile)

@admin_bp.route('/employer-verification/<int:profile_id>/approve', methods=['POST'])
@login_required
def approve_employer_profile(profile_id):
    """Approve an employer profile."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    from models import EmployerProfile
    profile = EmployerProfile.query.get_or_404(profile_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    try:
        profile.verification_status = 'approved'
        profile.is_verified = True
        profile.verified_by = current_user.id
        profile.verified_at = datetime.utcnow()
        if admin_notes:
            profile.admin_notes = admin_notes
        profile.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Employer profile for {profile.company_name} has been approved successfully.', 'success')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while approving the profile. Please try again.', 'error')

    return redirect(url_for('admin.verification_management'))

@admin_bp.route('/employer-verification/<int:profile_id>/reject', methods=['POST'])
@login_required
def reject_employer_profile(profile_id):
    """Reject an employer profile."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    from models import EmployerProfile
    profile = EmployerProfile.query.get_or_404(profile_id)
    admin_notes = request.form.get('admin_notes', '').strip()

    if not admin_notes:
        flash('Please provide a reason for rejection.', 'error')
        return redirect(url_for('admin.review_employer_profile', profile_id=profile_id))

    try:
        profile.verification_status = 'rejected'
        profile.is_verified = False
        profile.verified_by = current_user.id
        profile.verified_at = datetime.utcnow()
        profile.admin_notes = admin_notes
        profile.updated_at = datetime.utcnow()

        db.session.commit()

        flash(f'Employer profile for {profile.company_name} has been rejected.', 'warning')

    except Exception as e:
        db.session.rollback()
        flash('An error occurred while rejecting the profile. Please try again.', 'error')

    return redirect(url_for('admin.verification_management'))

@admin_bp.route('/view-document/<int:profile_id>/<document_type>')
@login_required
def view_document(profile_id, document_type):
    """View uploaded documents."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    profile = VeteranProfile.query.get_or_404(profile_id)

    base_folder = os.path.join(current_app.root_path, 'static', 'uploads')

    if document_type == 'discharge':
        filename = profile.discharge_document
        directory = base_folder

    elif document_type == 'id':
        filename = profile.id_document
        directory = base_folder

    elif document_type == 'resume':
        filename = profile.resume_file

        if not filename:
            flash('Resume not found.', 'error')
            return redirect(url_for('admin.review_profile', profile_id=profile_id))

        # 🔥 FIX: split path correctly
        if filename.startswith('resumes/'):
            directory = os.path.join(base_folder, 'resumes')
            filename = filename.replace('resumes/', '')
        else:
            directory = os.path.join(base_folder, 'resumes')

    else:
        flash('Invalid document type.', 'error')
        return redirect(url_for('admin.review_profile', profile_id=profile_id))

    # ✅ Final safety check
    full_path = os.path.join(directory, filename)

    if not os.path.exists(full_path):
        print("❌ FILE NOT FOUND:", full_path)
        flash('File not found on server.', 'error')
        return redirect(url_for('admin.review_profile', profile_id=profile_id))

    return send_from_directory(directory, filename, as_attachment=False)

@admin_bp.route('/verification/stats')
@login_required
def verification_stats():
    """Get verification statistics."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    stats = {
        'total_profiles': VeteranProfile.query.count(),
        'pending': VeteranProfile.query.filter_by(verification_status='pending').count(),
        'approved': VeteranProfile.query.filter_by(verification_status='approved').count(),
        'rejected': VeteranProfile.query.filter_by(verification_status='rejected').count(),
    }

    return render_template('admin/verification_stats.html', stats=stats)