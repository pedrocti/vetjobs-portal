# routes/dashboard.py
from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    current_app,
    abort,
)
from flask_login import login_required, current_user
from app import db
from utils.helpers import (
    get_profile_completion,
    sanitize_input,
    validate_email,
    validate_phone,
    log_security_event,
)
from werkzeug.security import generate_password_hash, check_password_hash

dashboard_bp = Blueprint("dashboard", __name__)


# ═══════════════════════════════════════════════════════════════
# INDEX — route to correct dashboard
# ═══════════════════════════════════════════════════════════════
@dashboard_bp.route("/")
@login_required
def index():
    current_app.logger.info(
        f"[Dashboard access] User={current_user.username}, "
        f"Type={current_user.user_type}, Authenticated={current_user.is_authenticated}"
    )

    if current_user.is_veteran():
        return redirect(url_for("dashboard.veteran"))
    elif current_user.is_employer():
        return redirect(url_for("dashboard.employer"))
    elif current_user.is_admin():
        return redirect(url_for("dashboard.admin"))
    elif current_user.user_type in ["partner", "trainer", "training_partner"]:
        return redirect(url_for("training_partners.dashboard"))

    current_app.logger.warning(
        f"Invalid user type for {current_user.username}: {current_user.user_type}"
    )
    flash("Invalid user type.", "error")
    return redirect(url_for("main.index"))


# ═══════════════════════════════════════════════════════════════
# VETERAN DASHBOARD
# Gate: onboarding_completed must be True.
# If not → redirect to complete profile.
# ═══════════════════════════════════════════════════════════════
@dashboard_bp.route("/veteran")
@login_required
def veteran():
    if not current_user.is_veteran():
        flash("Access denied. Veterans only.", "error")
        return redirect(url_for("main.index"))

    # ── Profile completion gate ────────────────────────────────
    # onboarding_completed is set to True in veteran.complete_profile
    # on successful form submission. Using this flag avoids recalculating
    # profile_completion_percentage() on every dashboard load.
    if not current_user.onboarding_completed:
        flash(
            "Please complete your profile before accessing your dashboard.",
            "info"
        )
        return redirect(url_for("veteran.complete_profile"))

    from models import JobApplication, JobPosting, PaymentSetting

    recent_applications = (
        JobApplication.query.filter_by(veteran_id=current_user.id)
        .order_by(JobApplication.created_at.desc())
        .limit(5)
        .all()
    )

    stats = {
        "total_applications": JobApplication.query.filter_by(
            veteran_id=current_user.id
        ).count(),
        "interviews": JobApplication.query.filter_by(
            veteran_id=current_user.id, status="interview"
        ).count(),
        "active_jobs": JobPosting.query.filter_by(
            is_active=True, status="approved"
        ).count(),
        "profile_completion": get_profile_completion(current_user),
    }

    verification_fee = PaymentSetting.get_setting("verification_fee", 2000)
    boost_fee        = PaymentSetting.get_setting("boost_fee", 1000)

    profile = getattr(current_user, "veteran_profile", None)

    has_skills = False
    if profile:
        has_skills = bool(
            (profile.skills or "").strip() or (profile.certifications or "").strip()
        )

    return render_template(
        "dashboards/veteran.html",
        recent_applications=recent_applications,
        stats=stats,
        verification_fee=verification_fee,
        boost_fee=boost_fee,
        has_skills=has_skills,
    )


# ═══════════════════════════════════════════════════════════════
# EMPLOYER DASHBOARD
# Gate: profile_completed must be True (already existed — kept as-is)
# ═══════════════════════════════════════════════════════════════
@dashboard_bp.route("/employer")
@login_required
def employer():
    if not current_user.is_employer():
        flash("Access denied. Employers only.", "error")
        return redirect(url_for("main.index"))

    from models import (
        EmployerProfile,
        JobPosting,
        JobApplication,
        User,
        PaymentSetting,
        Subscription,
    )

    # ── Profile completion gate ────────────────────────────────
    employer_profile = EmployerProfile.query.filter_by(user_id=current_user.id).first()
    if not employer_profile or not employer_profile.profile_completed:
        flash(
            "Please complete your company profile to access your dashboard.",
            "info"
        )
        return redirect(url_for("employer.complete_profile"))

    # ── Status alerts ──────────────────────────────────────────
    if current_user.employer_status == "pending":
        flash("Your account is pending admin approval.", "info")
    elif current_user.employer_status == "rejected":
        flash("Your account has been rejected. Contact support.", "error")

    # ── Subscription ───────────────────────────────────────────
    subscription = Subscription.get_or_create_for_user(current_user)

    # ── Feature flags ──────────────────────────────────────────
    can_post_job      = subscription.can_post_job(current_user.id)
    can_contact       = subscription.can_contact()
    can_export        = bool(subscription.can_export_resumes) and subscription.is_active()
    can_use_analytics = subscription.can_use_feature("analytics_access")
    can_use_ai        = subscription.can_use_feature("ai_talent_suggestions")
    can_access_cv     = subscription.is_cv_access_granted()

    plan_features = (
        Subscription.get_plan_features(subscription.plan_type) if subscription else {}
    )

    # ── Stats ──────────────────────────────────────────────────
    stats = {
        "active_jobs": JobPosting.query.filter_by(
            posted_by=current_user.id, is_active=True, status="approved"
        ).count(),
        "total_applications": JobApplication.query.join(JobPosting)
        .filter(JobPosting.posted_by == current_user.id)
        .count(),
        "interviews": JobApplication.query.join(JobPosting)
        .filter(
            JobPosting.posted_by == current_user.id,
            JobApplication.status == "interview",
        )
        .count(),
        "total_veterans": User.query.filter_by(user_type="veteran").count(),
    }

    # ── Recent applications ────────────────────────────────────
    recent_applications = (
        db.session.query(JobApplication, JobPosting, User)
        .join(JobPosting, JobApplication.job_id == JobPosting.id)
        .join(User, JobApplication.veteran_id == User.id)
        .filter(JobPosting.posted_by == current_user.id)
        .order_by(JobApplication.created_at.desc())
        .limit(5)
        .all()
    )

    # ── Recent jobs ────────────────────────────────────────────
    recent_jobs = (
        JobPosting.query.filter_by(posted_by=current_user.id)
        .order_by(JobPosting.created_at.desc())
        .limit(5)
        .all()
    )

    # ── AI suggested veterans (Pro/Enterprise only) ────────────
    suggested_veterans = []
    if can_use_ai:
        from services.search_service import search_service
        suggested_veterans = search_service.get_suggested_veterans_for_employer(
            employer_id=current_user.id, limit=6
        )

    # ── Plan pricing ───────────────────────────────────────────
    starter_plan_amount      = PaymentSetting.get_setting("starter_plan_amount", 20000)
    professional_plan_amount = PaymentSetting.get_setting("professional_plan_amount", 40000)
    enterprise_plan_amount   = PaymentSetting.get_setting("enterprise_plus_plan_amount", 120000)

    return render_template(
        "dashboards/employer.html",
        employer_profile=employer_profile,
        stats=stats,
        subscription=subscription,
        plan_features=plan_features,
        can_post_job=can_post_job,
        can_contact=can_contact,
        can_export=can_export,
        can_use_analytics=can_use_analytics,
        can_use_ai=can_use_ai,
        can_access_cv=can_access_cv,
        job_boosts=subscription.job_boosts if subscription else 0,
        starter_plan_amount=starter_plan_amount,
        professional_plan_amount=professional_plan_amount,
        enterprise_plan_amount=enterprise_plan_amount,
        recent_jobs=recent_jobs,
        recent_applications=recent_applications,
        suggested_veterans=suggested_veterans,
    )


# ═══════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════
@dashboard_bp.route("/admin")
@login_required
def admin():
    if not current_user.is_admin():
        flash("Access denied. Administrators only.", "error")
        return redirect(url_for("main.index"))
    return render_template("dashboards/admin.html")


# ═══════════════════════════════════════════════════════════════
# PROFILE PAGE
# ═══════════════════════════════════════════════════════════════
@dashboard_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    from models import EmployerProfile
    from routes.employer import handle_employer_profile_form

    if current_user.is_employer():
        profile = EmployerProfile.query.filter_by(user_id=current_user.id).first()

        if not profile:
            profile = EmployerProfile(user_id=current_user.id)
            db.session.add(profile)
            db.session.commit()

        if request.method == "POST":
            try:
                current_user.first_name = sanitize_input(request.form.get("first_name", ""))
                current_user.last_name  = sanitize_input(request.form.get("last_name", ""))
                current_user.email      = sanitize_input(request.form.get("email", ""))
                current_user.phone      = sanitize_input(request.form.get("phone", ""))
                current_user.location   = sanitize_input(request.form.get("location", ""))
                current_user.bio        = sanitize_input(request.form.get("bio", ""))

                if not validate_email(current_user.email):
                    flash("Invalid email format.", "error")
                    return redirect(url_for("dashboard.profile"))

                if current_user.phone and not validate_phone(current_user.phone):
                    flash("Invalid phone number.", "error")
                    return redirect(url_for("dashboard.profile"))

                updated_profile = handle_employer_profile_form(profile, is_edit=True)

                if not updated_profile:
                    return render_template(
                        "dashboards/profile.html",
                        profile=profile,
                        is_employer=True
                    )

                db.session.commit()

                ip_address = request.environ.get(
                    "HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR")
                )
                log_security_event(
                    "employer_profile_updated",
                    current_user.id,
                    {"company_name": profile.company_name},
                    ip_address,
                )

                flash("Profile updated successfully.", "success")
                return redirect(url_for("dashboard.profile"))

            except Exception as e:
                db.session.rollback()
                current_app.logger.error(e)
                flash("Error updating employer profile.", "error")

        return render_template(
            "dashboards/profile.html",
            profile=profile,
            is_employer=True
        )

    # ── Non-employer ───────────────────────────────────────────
    if request.method == "POST":
        try:
            current_user.first_name = sanitize_input(request.form.get("first_name", ""))
            current_user.last_name  = sanitize_input(request.form.get("last_name", ""))
            current_user.email      = sanitize_input(request.form.get("email", ""))
            current_user.phone      = sanitize_input(request.form.get("phone", ""))
            current_user.location   = sanitize_input(request.form.get("location", ""))
            current_user.bio        = sanitize_input(request.form.get("bio", ""))

            if not validate_email(current_user.email):
                flash("Invalid email format.", "error")
                return redirect(url_for("dashboard.profile"))

            if current_user.phone and not validate_phone(current_user.phone):
                flash("Invalid phone number.", "error")
                return redirect(url_for("dashboard.profile"))

            db.session.commit()
            flash("Profile updated successfully!", "success")
        except Exception:
            db.session.rollback()
            flash("Error updating profile.", "error")

        return redirect(url_for("dashboard.profile"))

    return render_template("dashboards/profile.html", is_employer=False)


# ═══════════════════════════════════════════════════════════════
# CHANGE PASSWORD
# ═══════════════════════════════════════════════════════════════
@dashboard_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    try:
        current_password  = request.form.get("current_password", "").strip()
        new_password      = request.form.get("new_password", "").strip()
        confirm_password  = request.form.get("confirm_new_password", "").strip()

        if not current_password or not check_password_hash(
            current_user.password_hash, current_password
        ):
            flash("Current password is incorrect.", "error")
            return redirect(url_for("dashboard.profile"))

        if not new_password or len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
            return redirect(url_for("dashboard.profile"))

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("dashboard.profile"))

        current_user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash("Password changed successfully!", "success")
    except Exception:
        db.session.rollback()
        flash("Error changing password.", "error")

    return redirect(url_for("dashboard.profile"))