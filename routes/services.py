from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, CVOptimizationRequest, PaymentSetting

services_bp = Blueprint('services', __name__)


# ==============================
# 📄 CV OPTIMIZATION PAGE (GET)
# ==============================
@services_bp.route('/cv-optimize', methods=['GET'])
@login_required
def cv_optimize_page():

    profile = getattr(current_user, 'veteran_profile', None)

    cv_file = None

    if profile:
        # SAFE: match REAL database field
        cv_file = (
            getattr(profile, 'resume_file', None) or
            getattr(profile, 'resume', None) or
            getattr(profile, 'cv_file', None) or
            getattr(profile, 'file_path', None)
        )

    # ✅ ADD THIS (dynamic pricing from admin)
    cv_price = PaymentSetting.get_setting("cv_optimization_fee", 5000)

    return render_template(
        'services/cv_optimize.html',
        cv_file=cv_file,
        cv_price=cv_price
    )


# ==============================
# 💳 REDIRECT TO PAYMENT (POST)
# ==============================
@services_bp.route('/cv-optimize', methods=['POST'])
@login_required
def request_cv_optimization():

    profile = getattr(current_user, 'veteran_profile', None)
    cv_file = getattr(profile, 'resume_file', None)

    # 🔒 VALIDATION
    if not profile or not cv_file:
        flash('Please upload a CV first.', 'danger')
        return redirect(url_for('dashboard.veteran'))

    # 🚀 Redirect to payment (NO DB INSERT HERE)
    return redirect(url_for(
        'payments.init_payment',
        feature='cv_optimization'
    ))


# ==============================
# 🧠 CREATE REQUEST AFTER PAYMENT
# ==============================
def create_cv_optimization_request(user):

    profile = getattr(user, 'veteran_profile', None)
    cv_file = getattr(profile, 'resume_file', None)

    if not profile or not cv_file:
        return False

    # 🚫 Prevent duplicate submissions
    existing = CVOptimizationRequest.query.filter_by(
        user_id=user.id,
        cv_file=cv_file
    ).first()

    if existing:
        return True

    try:
        request_entry = CVOptimizationRequest(
            user_id=user.id,
            cv_file=cv_file
        )

        db.session.add(request_entry)
        db.session.commit()
        return True

    except Exception:
        db.session.rollback()
        return False


# ==============================
# 🚀 JOB-READY PACKAGE PAGE
# ==============================
@services_bp.route('/job-ready', methods=['GET'])
def job_ready_package():
    job_ready_fee = PaymentSetting.get_setting("job_ready_package_fee", 4500)
    return render_template(
        'services/job_ready_package.html',
        job_ready_fee=job_ready_fee
    )


@services_bp.route('/job-ready/checkout', methods=['POST'])
@login_required
def job_ready_checkout():
    if not current_user.is_veteran():
        flash('This package is for veterans only.', 'danger')
        return redirect(url_for('services.job_ready_package'))

    profile = getattr(current_user, 'veteran_profile', None)
    if not profile:
        flash('Please complete your profile first.', 'warning')
        return redirect(url_for('veteran.complete_profile'))

    if getattr(profile, 'job_ready_package_active', False):
        flash('You already have an active Job-Ready package!', 'info')
        return redirect(url_for('dashboard.veteran'))

    return redirect(url_for('payments.init_payment', feature='job_ready_package'))