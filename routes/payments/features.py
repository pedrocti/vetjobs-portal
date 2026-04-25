from decimal import Decimal, InvalidOperation
from models import PaymentSetting
from flask import request, jsonify, url_for, current_app
from models import Payment
from app import db
from services.payment_gateway import payment_gateway_service

from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    current_app,
    jsonify,
)
from flask_login import login_required, current_user
from models import Payment, Subscription, PaymentSetting, VeteranProfile, User
from app import db
from services.notification_service import notification_service
from services.payment_gateway import payment_gateway_service
from datetime import datetime, timedelta
import json
from . import payments_bp


@payments_bp.route("/feature/init", methods=["GET"])
@login_required
def init_payment():
    """Initialize payment for premium features like modern resume or professional review."""
    try:
        # 1) Get feature name from the URL (default to 'resume')
        feature = request.args.get("feature", "resume").strip().lower()

        raw_amount = request.args.get("amount", type=str)

        # Map feature name -> PaymentSetting key
        feature_setting_map = {
            "resume": "resume_fee",
            "review": "review_fee",
            "ai_flyer": "ai_flyer_fee",
            "cv_optimization": "cv_optimization_fee",
        }

        setting_key = feature_setting_map.get(feature, None)

        # If amount provided in query param, try to use it (but validate below)
        amount_value = None
        if raw_amount:
            try:
                amount_value = Decimal(raw_amount)
            except (InvalidOperation, TypeError):
                amount_value = None

        # If no valid amount from query param, look up PaymentSetting
        if amount_value is None:
            if setting_key:
                # PaymentSetting returns a number or string; default to 0 if missing
                amt_from_setting = PaymentSetting.get_setting(setting_key, default=0)
                try:
                    amount_value = Decimal(str(amt_from_setting))
                except (InvalidOperation, TypeError):
                    amount_value = Decimal(0)
            else:
                # No known setting key for this feature -> error
                flash("Unknown feature or missing configuration.", "error")
                return redirect(url_for("main.index"))

        # Ensure amount is positive
        if amount_value <= 0:
            flash("Invalid payment amount configured. Please contact admin.", "error")
            return redirect(url_for("main.index"))

        # Convert to integer if your gateway expects the smallest currency unit (kobo).
        # IMPORTANT: payment_gateway_service.initialize_payment should handle currency units,
        # but if it expects integer kobo, you would send int(amount_value * 100).
        # Here we pass the Decimal amount and let the gateway service decide.
        amount_for_payment = amount_value

        # Create a unique reference
        reference = payment_gateway_service.generate_reference("FEAT")

        # Create a payment record (use Decimal for amount)
        payment = Payment(
            user_id=current_user.id,
            reference=reference,
            amount=amount_for_payment,
            payment_type="feature",
            description=f"Payment for {feature.replace('_', ' ').title()}",
            status="pending",
            payment_metadata={},  # start with an empty metadata object
        )
        # Store useful metadata
        metadata = {
            "payment_id_temp": None,  # we'll update after flush
            "user_id": current_user.id,
            "feature": feature,
            "user_name": getattr(current_user, "full_name", current_user.email),
        }
        payment.payment_metadata = metadata

        db.session.add(payment)
        db.session.flush()  # get payment.id

        # update metadata with real payment id
        payment.payment_metadata["payment_id"] = payment.id

        callback_url = url_for(
            "payments.verify_payment", reference=reference, _external=True
        )

        # Initialize via Paystack/Flutterwave using your payment gateway service
        success, response = payment_gateway_service.initialize_payment(
            email=current_user.email,
            amount=amount_for_payment,
            reference=reference,
            callback_url=callback_url,
            metadata=payment.payment_metadata,
        )

        if success:
            # Save gateway-specific reference into metadata so we don't rely on non-existent fields
            gateway_ref = (
                response.get("reference")
                or response.get("tx_ref")
                or response.get("id")
                or None
            )
            if gateway_ref:
                payment.payment_metadata["gateway_reference"] = gateway_ref

                # If current gateway is paystack, also save to paystack_reference column for admin display
                current_gateway = PaymentSetting.get_setting(
                    "payment_gateway", "paystack"
                )
                if current_gateway == "paystack":
                    payment.paystack_reference = gateway_ref

            db.session.commit()

            # Redirect user to the provider's checkout URL (authorization_url for Paystack, link for Flutterwave)
            redirect_url = (
                response.get("authorization_url")
                or response.get("link")
                or response.get("data", {}).get("authorization_url")
            )
            if redirect_url:
                return redirect(redirect_url)
            else:
                flash(
                    "Payment initialized but no redirect URL returned by the gateway.",
                    "warning",
                )
                return redirect(url_for("main.index"))
        else:
            db.session.rollback()
            flash(response.get("error", "Payment initialization failed"), "error")
            return redirect(url_for("main.index"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Feature payment initialization error: {str(e)}")
        flash("Internal server error during payment initialization.", "error")
        return redirect(url_for("main.index"))


