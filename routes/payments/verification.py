from flask import redirect, url_for, flash, current_app
from datetime import datetime, timedelta
from models import Payment, Subscription, User
from app import db
from services.payment_gateway import payment_gateway_service
from services.notification_service import notification_service
from . import payments_bp


@payments_bp.route("/verify/<string:reference>", methods=["GET"])
def verify_payment(reference):
    try:
        success, result = payment_gateway_service.verify_payment(reference)

        payment = Payment.query.filter_by(reference=reference).first()
        if not payment:
            current_app.logger.warning(f"No Payment found for reference {reference}")
            return redirect(url_for("main.payment_failed"))

        if not success:
            payment.status = "failed"
            db.session.commit()
            return redirect(url_for("main.payment_failed"))

        status = result.get("status")
        if status not in ["success", "successful"]:
            payment.status = "failed"
            payment.paystack_status = status
            db.session.commit()
            return redirect(url_for("main.payment_failed"))

        # Payment confirmed
        payment.status = "success"
        payment.paystack_status = status
        metadata = payment.payment_metadata or {}
        feature  = metadata.get("feature")

        # ── 1. DONATION ──────────────────────────────────────────
        if payment.payment_type == "donation":
            try:
                email         = metadata.get("email")
                donation_type = metadata.get("type")
                if email:
                    notification_service.send_email(
                        to=email,
                        subject="Thank You for Your Donation — VetJobPortal",
                        body=f"Thank you for your generous donation.\n\nDonation type: {donation_type}\n\nYour support helps veterans rebuild their lives."
                    )
                current_app.logger.info(f"Donation OK | ref={payment.reference} amount={payment.amount}")
            except Exception as e:
                current_app.logger.error(f"Donation email error: {e}")

        # ── 2. SUBSCRIPTION ──────────────────────────────────────
        elif payment.payment_type == "subscription":
            plan_type     = metadata.get("plan_type")
            billing_cycle = metadata.get("billing_cycle", "monthly")
            user          = User.query.get(payment.user_id)

            if not plan_type or not user:
                current_app.logger.error(f"Subscription missing plan_type={plan_type} user={payment.user_id}")
                db.session.commit()
                flash("Payment received but plan details were missing. Please contact support.", "warning")
                return redirect(url_for("main.payment_failed"))

            from models.subscription import Subscription as Sub
            features      = Sub.get_plan_features(plan_type)
            duration_map  = {"monthly": 30, "6_months": 182, "yearly": 365}
            duration_days = duration_map.get(billing_cycle, 30)
            now           = datetime.utcnow()

            existing_sub = (
                Subscription.query.filter_by(user_id=payment.user_id)
                .order_by(Subscription.id.desc())
                .first()
            )

            if existing_sub:
                existing_sub.plan_type              = plan_type
                existing_sub.amount                 = payment.amount
                existing_sub.billing_cycle          = billing_cycle
                existing_sub.status                 = "active"
                existing_sub.started_at             = now
                existing_sub.expires_at             = now + timedelta(days=duration_days)
                existing_sub.updated_at             = now
                existing_sub.max_job_posts          = features.get("max_job_posts", 1)
                existing_sub.can_contact_candidates = features.get("can_contact_candidates", False)
                existing_sub.can_export_resumes     = features.get("can_export_resumes", False)
                existing_sub.priority_support       = features.get("priority_support", False)
                existing_sub.analytics_access       = features.get("analytics_access", False)
                existing_sub.team_accounts          = features.get("team_accounts", False)
                existing_sub.job_boosts             = features.get("job_boosts", 0)
                existing_sub.smart_candidate_matching = features.get("smart_candidate_matching", False)
            else:
                new_sub        = Sub.create_for_user(user=user, plan_type=plan_type, billing_cycle=billing_cycle, auto_renew=True)
                new_sub.amount = payment.amount

            db.session.commit()
            current_app.logger.info(f"Subscription activated: user={payment.user_id} plan={plan_type}")

            # Confirmation email
            try:
                from services.email_service import EmailService
                plan_name = features.get("name", plan_type.replace("_", " ").title())
                EmailService().send_notification_email(
                    user=user,
                    subject=f"Your {plan_name} is now active — VetJobPortal",
                    body=(
                        f"Your {plan_name} subscription has been activated.\n\n"
                        f"Billing cycle: {billing_cycle.replace('_', ' ').title()}\n"
                        f"Amount paid: ₦{int(payment.amount):,}\n\n"
                        "Log in to your dashboard to start hiring."
                    )
                )
            except Exception as e:
                current_app.logger.warning(f"Subscription email failed: {e}")

            flash("Subscription activated successfully. Welcome to your new plan!", "success")
            return redirect(url_for("main.success"))

        # ── 3. CV OPTIMIZATION ───────────────────────────────────
        elif payment.payment_type == "feature" and feature == "cv_optimization":
            try:
                from routes.services import create_cv_optimization_request
                user = User.query.get(payment.user_id)
                if user:
                    create_cv_optimization_request(user)
                flash("CV optimization request submitted! Our team will be in touch shortly.", "success")
            except Exception as e:
                current_app.logger.error(f"CV optimization error: {e}")

        # ── 4. JOB-READY PACKAGE ─────────────────────────────────
        elif payment.payment_type == "feature" and feature == "job_ready_package":
            try:
                from routes.services import create_cv_optimization_request
                from models import VeteranProfile
                user = User.query.get(payment.user_id)
                if user:
                    profile = VeteranProfile.query.filter_by(user_id=user.id).first()
                    if profile:
                        profile.job_ready_package_active = True
                        profile.veteran_tier             = "verified"
                        profile.is_verified              = True
                        profile.boost_profile(days=7)
                    create_cv_optimization_request(user)
                flash("You are now Job-Ready! Profile upgraded, boosted for 7 days, and CV queued for optimisation.", "success")
            except Exception as e:
                current_app.logger.error(f"Job-Ready activation error: {e}")

        # ── 5. BOOST ─────────────────────────────────────────────
        elif payment.payment_type == "boost":
            try:
                from models import VeteranProfile
                user = User.query.get(payment.user_id)
                if user:
                    profile = VeteranProfile.query.filter_by(user_id=user.id).first()
                    if profile:
                        profile.boost_profile(days=7)
                flash("Profile boosted for 7 days!", "success")
            except Exception as e:
                current_app.logger.error(f"Boost activation error: {e}")

        db.session.commit()
        return redirect(url_for("main.success"))

    except Exception as e:
        current_app.logger.exception(f"Payment verification failed: {e}")
        db.session.rollback()
        return redirect(url_for("main.payment_failed"))
