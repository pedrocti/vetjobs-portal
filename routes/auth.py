# routes/auth.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
from models import db, User, VeteranProfile, EmployerProfile, PasswordResetToken
from models.subscription import Subscription
from services.brevo_service import BrevoService

auth_bp = Blueprint("auth", __name__)


# ═══════════════════════════════════════════════════════════════
# HELPER: BUILD EXTERNAL URL
# ═══════════════════════════════════════════════════════════════
def build_external_url(endpoint, **values):
    base_url = current_app.config["BASE_URL"]
    return f"{base_url}{url_for(endpoint, **values)}"


# ═══════════════════════════════════════════════════════════════
# REGISTER
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":

        first_name = (request.form.get("first_name") or "").strip()
        last_name  = (request.form.get("last_name")  or "").strip()
        username   = (request.form.get("username")   or "").strip()
        email      = (request.form.get("email")      or "").strip().lower()
        phone      = (request.form.get("phone")      or "").strip()
        country    = (request.form.get("country")    or "").strip()
        user_type  = request.form.get("user_type")
        password   = request.form.get("password")
        confirm    = request.form.get("confirm_password")

        if not all([username, email, password, user_type]):
            flash("Please complete all required fields.", "danger")
            return redirect(url_for("auth.register"))

        if password is None:
            flash("Password is required.", "danger")
            return redirect(url_for("auth.register"))

        password = password.strip()

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for("auth.register"))

        if User.query.filter(
            (User.username == username) | (User.email == email)
        ).first():
            flash("Username or email is already taken.", "danger")
            return redirect(url_for("auth.register"))

        # ── Create user ────────────────────────────────────────
        user = User()
        user.username      = username
        user.email         = email
        user.first_name    = first_name or username.split("@")[0].capitalize()
        user.last_name     = last_name
        user.user_type     = user_type
        user.created_at    = datetime.utcnow()
        user.password_hash = generate_password_hash(password)
        user.is_verified   = False

        db.session.add(user)
        db.session.flush()

        # ── Create profile ─────────────────────────────────────
        if user_type == "veteran":
            profile            = VeteranProfile(user_id=user.id)
            profile.created_at = datetime.utcnow()
            profile.updated_at = datetime.utcnow()
            db.session.add(profile)

        elif user_type == "employer":
            profile            = EmployerProfile()
            profile.user_id    = user.id
            profile.created_at = datetime.utcnow()
            profile.updated_at = datetime.utcnow()

            subscription = Subscription.create_for_user(user, plan_type="free")

            profile.subscription_active     = True
            profile.subscription_plan       = "free"
            profile.subscription_expires_at = subscription.expires_at

            db.session.add(profile)

        else:
            db.session.rollback()
            flash("Invalid enrollment type selected.", "danger")
            return redirect(url_for("auth.register"))

        db.session.commit()

        # ── Send verification email via Brevo ──────────────────
        # NOTE: Brevo contact sync happens AFTER verification (confirm user is real)
        try:
            token       = user.generate_verification_token()
            verify_link = build_external_url("auth.verify_email", token=token)
            sent        = BrevoService().send_verification_email(user, verify_link)

            if not sent:
                current_app.logger.error(
                    f"[AUTH] Verification email failed for {user.email} — "
                    "check Brevo API key, template #11 is Active, sender is verified."
                )
        except Exception as e:
            current_app.logger.error(f"[AUTH] Verification email exception: {e}")

        flash("Registration successful! Please check your email to verify your account.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


# ═══════════════════════════════════════════════════════════════
# EMAIL VERIFICATION
# ─ Contact synced to Brevo HERE (after confirmation user is real)
# ─ Welcome email fires HERE
# ─ Redirect goes to complete profile, NOT dashboard
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/verify-email/<token>")
def verify_email(token):
    user = User.verify_verification_token(token)

    if not user:
        flash(
            "This verification link is invalid or has expired. "
            "Request a new one below.",
            "danger"
        )
        return redirect(url_for("auth.resend_verification"))

    if user.is_verified:
        flash("Your email is already verified. Please log in.", "info")
        return redirect(url_for("auth.login"))

    user.is_verified = True
    db.session.commit()

    brevo = BrevoService()

    # ── Sync contact to Brevo CRM now that user is confirmed ──
    # This is the correct moment — unverified users shouldn't be in your lists
    try:
        synced = brevo.add_contact(user)
        if synced:
            current_app.logger.info(f"[AUTH] Brevo contact synced after verification: {user.email}")
        else:
            current_app.logger.warning(f"[AUTH] Brevo contact sync failed for: {user.email}")
    except Exception as e:
        current_app.logger.warning(f"[AUTH] Brevo contact sync exception: {e}")

    # ── Send welcome email ─────────────────────────────────────
    try:
        brevo.send_welcome_email(user)
    except Exception as e:
        current_app.logger.warning(f"[AUTH] Welcome email failed: {e}")

    flash("Email verified successfully! Let's get your profile set up.", "success")

    # ── Redirect to profile completion, not dashboard ──────────
    if user.user_type == "veteran":
        return redirect(url_for("veteran.complete_profile"))
    elif user.user_type == "employer":
        return redirect(url_for("employer.complete_profile"))
    else:
        return redirect(url_for("auth.login"))


# ═══════════════════════════════════════════════════════════════
# RESEND VERIFICATION EMAIL
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/resend-verification", methods=["GET", "POST"])
def resend_verification():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not email:
            flash("Please enter your email address.", "danger")
            return redirect(url_for("auth.resend_verification"))

        generic_message = (
            "If that email is registered and unverified, "
            "a new verification link has been sent. Please check your inbox."
        )

        user = User.query.filter_by(email=email).first()

        if not user:
            flash(generic_message, "info")
            return redirect(url_for("auth.login"))

        if user.is_verified:
            flash("This account is already verified. Please log in.", "info")
            return redirect(url_for("auth.login"))

        # ── Rate limit: 2 minute cooldown ──────────────────────
        session_key  = f"verify_resent_{email}"
        last_sent    = session.get(session_key)
        cooldown     = timedelta(minutes=2)

        if last_sent:
            last_sent_dt = datetime.fromisoformat(last_sent)
            elapsed      = datetime.utcnow() - last_sent_dt
            if elapsed < cooldown:
                remaining = int((cooldown - elapsed).total_seconds())
                flash(
                    f"Please wait {remaining} seconds before requesting another link.",
                    "warning"
                )
                return redirect(url_for("auth.resend_verification"))

        try:
            token       = user.generate_verification_token()
            verify_link = build_external_url("auth.verify_email", token=token)
            sent        = BrevoService().send_verification_email(user, verify_link)

            if sent:
                session[session_key] = datetime.utcnow().isoformat()
                current_app.logger.info(f"[AUTH] Verification resent → {user.email}")
            else:
                current_app.logger.error(f"[AUTH] Verification resend failed → {user.email}")

        except Exception as e:
            current_app.logger.error(f"[AUTH] Resend verification exception: {e}")

        flash(generic_message, "info")
        return redirect(url_for("auth.login"))

    prefill_email = request.args.get("email", "")
    return render_template("auth/resend_verification.html", prefill_email=prefill_email)


# ═══════════════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)

    if request.method == "POST":
        identifier = (request.form.get("username") or request.form.get("email") or "").strip()
        password   = request.form.get("password")

        if not identifier or not password:
            flash("Username/email and password are required.", "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid username/email or password.", "danger")
            return redirect(url_for("auth.login"))

        if not user.is_verified:
            session["unverified_email"] = user.email
            flash("Please verify your email before logging in.", "verify")
            return redirect(url_for("auth.login"))

        session.pop("unverified_email", None)

        login_user(user)
        session["user_id"]   = user.id
        session["user_type"] = user.user_type

        flash(f"Welcome back, {user.first_name or user.username}!", "success")
        return _redirect_after_login(user)

    return render_template("auth/login.html")


def _redirect_after_login(user):
    """
    After login, check profile completion.
    Incomplete → complete profile page.
    Complete   → dashboard.
    """
    if user.user_type == "veteran":
        # Use onboarding_completed flag for efficiency
        if not user.onboarding_completed:
            flash("Please complete your profile to access your dashboard.", "info")
            return redirect(url_for("veteran.complete_profile"))
        return redirect(url_for("dashboard.veteran"))

    elif user.user_type == "employer":
        profile = getattr(user, "employer_profile", None)
        if not profile or not profile.profile_completed:
            flash("Please complete your company profile to access your dashboard.", "info")
            return redirect(url_for("employer.complete_profile"))
        return redirect(url_for("dashboard.employer"))

    elif user.user_type == "admin":
        return redirect(url_for("admin.dashboard"))

    return redirect(url_for("auth.logout"))


# ═══════════════════════════════════════════════════════════════
# LOGOUT
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/logout")
def logout():
    logout_user()
    session.clear()
    flash("You've been logged out.", "info")
    return redirect(url_for("auth.login"))


# ═══════════════════════════════════════════════════════════════
# FORGOT PASSWORD
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()

        if not email:
            flash("Please enter your registered email.", "danger")
            return redirect(url_for("auth.forgot_password"))

        generic_message = "If that email is registered, a reset link has been sent."

        user = User.query.filter_by(email=email).first()

        if not user:
            flash(generic_message, "info")
            return redirect(url_for("auth.login"))

        # ── Rate limit ──────────────────────────────────────────
        session_key  = f"reset_sent_{email}"
        last_sent    = session.get(session_key)
        cooldown     = timedelta(minutes=2)

        if last_sent:
            last_sent_dt = datetime.fromisoformat(last_sent)
            elapsed      = datetime.utcnow() - last_sent_dt
            if elapsed < cooldown:
                remaining = int((cooldown - elapsed).total_seconds())
                flash(
                    f"Please wait {remaining} seconds before requesting another reset email.",
                    "warning"
                )
                return redirect(url_for("auth.forgot_password"))

        try:
            token      = PasswordResetToken.generate_token(user)
            reset_link = build_external_url("auth.reset_password", token=token)

            sent = False

            if "password_reset" in BrevoService.TEMPLATES:
                sent = BrevoService().send_password_reset_email(user, reset_link)

            if not sent:
                from services.email_service import EmailService
                sent = EmailService().send_password_reset_email(user, reset_link)

            if sent:
                session[session_key] = datetime.utcnow().isoformat()
                current_app.logger.info(f"[AUTH] Password reset sent → {user.email}")
            else:
                current_app.logger.error(f"[AUTH] Password reset failed → {user.email}")

        except Exception as e:
            current_app.logger.error(f"[AUTH] Password reset exception: {e}")

        flash(generic_message, "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html")


# ═══════════════════════════════════════════════════════════════
# RESET PASSWORD
# ═══════════════════════════════════════════════════════════════
@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = PasswordResetToken.verify_token(token)

    if not user:
        flash(
            "This reset link is invalid or has expired. Please request a new one.",
            "danger"
        )
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password")
        confirm  = request.form.get("confirm_password")

        if not password or not confirm:
            flash("Please enter and confirm your new password.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        if password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "danger")
            return redirect(url_for("auth.reset_password", token=token))

        user.password_hash = generate_password_hash(password)
        PasswordResetToken.use_token(token)
        db.session.commit()

        flash("Password updated successfully. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html")