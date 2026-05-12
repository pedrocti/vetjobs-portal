from flask import (
    redirect,
    url_for,
    flash,
    current_app,
)
from datetime import datetime, timedelta

from models import Payment, Subscription, User
from app import db
from services.payment_gateway import payment_gateway_service
from services.notification_service import notification_service
from . import payments_bp


@payments_bp.route("/verify/<string:reference>", methods=["GET"])
def verify_payment(reference):
    """
    Verify payment after redirect from Paystack/Flutterwave.
    Handles:
    - Donations
    - Subscriptions
    - Feature payments (CV optimization)
    """

    try:
        success, result = payment_gateway_service.verify_payment(reference)

        payment = Payment.query.filter_by(reference=reference).first()

        if not payment:
            current_app.logger.warning(f"No Payment found for reference {reference}")
            return redirect(url_for("main.payment_failed"))

        # ==========================
        # GATEWAY FAILED
        # ==========================
        if not success:
            payment.status = "failed"
            db.session.commit()
            return redirect(url_for("main.payment_failed"))

        status = result.get("status")

        # ==========================
        # NOT SUCCESSFUL PAYMENT
        # ==========================
        if status not in ["success", "successful"]:
            payment.status = "failed"
            payment.paystack_status = status
            db.session.commit()
            return redirect(url_for("main.payment_failed"))

        # ==========================
        # PAYMENT SUCCESS
        # ==========================
        payment.status = "success"
        payment.paystack_status = status

        metadata = payment.payment_metadata or {}
        feature = metadata.get("feature")

        # =========================================================
        # 1. DONATION FLOW
        # =========================================================
        if payment.payment_type == "donation":
            try:
                email = metadata.get("email")
                donation_type = metadata.get("type")

                if email:
                    try:
                        notification_service.send_email(
                            to=email,
                            subject="Thank You for Your Donation ❤️",
                            body=f"""
Thank you for your generous donation.

Your support is helping veterans rebuild their lives.

Donation Type: {donation_type}
"""
                        )
                    except Exception as e:
                        current_app.logger.error(
                            f"Donation email failed: {str(e)}"
                        )

                current_app.logger.info(
                    f"Donation successful | Ref: {payment.reference} | Amount: {payment.amount}"
                )

            except Exception as e:
                current_app.logger.error(f"Donation processing error: {str(e)}")

        # =========================================================
        # 2. SUBSCRIPTION FLOW
        # =========================================================
        elif payment.payment_type == "subscription":
            try:
                plan_type = metadata.get("plan_type")
                billing_cycle = metadata.get("billing_cycle", "monthly")

                user = User.query.get(payment.user_id)

                existing_sub = (
                    Subscription.query.filter_by(user_id=payment.user_id)
                    .order_by(Subscription.id.desc())
                    .first()
                )

                now = datetime.utcnow()

                duration_map = {
                    "monthly": 30,
                    "6_months": 182,
                    "yearly": 365,
                }

                duration_days = duration_map.get(billing_cycle, 30)

                if existing_sub:
                    # UPDATE EXISTING SUBSCRIPTION
                    existing_sub.plan_type = plan_type
                    existing_sub.amount = payment.amount
                    existing_sub.billing_cycle = billing_cycle
                    existing_sub.status = "active"
                    existing_sub.started_at = now
                    existing_sub.expires_at = now + timedelta(days=duration_days)
                    existing_sub.updated_at = now
                else:
                    # CREATE NEW SUBSCRIPTION
                    new_sub = Subscription.create_for_user(
                        user=user,
                        plan_type=plan_type,
                        billing_cycle=billing_cycle,
                        auto_renew=True,
                    )
                    new_sub.amount = payment.amount

                flash("🎉 Subscription activated!", "success")

            except Exception as e:
                current_app.logger.error(f"Subscription processing error: {str(e)}")

        # =========================================================
        # 3. FEATURE FLOW (CV OPTIMIZATION)
        # =========================================================
        elif payment.payment_type == "feature" and feature == "cv_optimization":
            try:
                from routes.services import create_cv_optimization_request

                user = User.query.get(payment.user_id)

                if user:
                    create_cv_optimization_request(user)

                flash("CV optimization request submitted successfully!", "success")

            except Exception as e:
                current_app.logger.error(f"CV optimization error: {str(e)}")

        # =========================================================
        # 4. JOB-READY PACKAGE FLOW
        # =========================================================
        elif payment.payment_type == "feature" and feature == "job_ready_package":
            try:
                from routes.services import create_cv_optimization_request
                from models import VeteranProfile

                user = User.query.get(payment.user_id)

                if user:
                    profile = VeteranProfile.query.filter_by(user_id=user.id).first()
                    if profile:
                        profile.job_ready_package_active = True
                        profile.veteran_tier = 'verified'
                        profile.is_verified = True
                        profile.boost_profile(days=7)

                    create_cv_optimization_request(user)

                flash("You are now Job-Ready! Your profile has been upgraded, boosted for 7 days, and your CV is queued for optimization.", "success")

            except Exception as e:
                current_app.logger.error(f"Job-Ready Package activation error: {str(e)}")

        # =========================================================
        # 5. BOOST FLOW
        # =========================================================
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
                current_app.logger.error(f"Boost activation error: {str(e)}")

        # ==========================
        # FINAL SAVE
        # ==========================
        db.session.commit()
        return redirect(url_for("main.success"))

    except Exception as e:
        current_app.logger.exception(f"Payment verification failed: {str(e)}")
        db.session.rollback()
        return redirect(url_for("main.payment_failed"))