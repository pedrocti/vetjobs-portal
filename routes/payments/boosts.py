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

# Default payment amounts (can be overridden by admin settings)
DEFAULT_BOOST_FEE = 1000  # ₦1,000

# ==============================
#   VETERAN BOOST PAYMENT
# ==============================
@payments_bp.route("/veteran/boost/pay")
@login_required
def veteran_boost_payment():
    if not current_user.is_veteran():
        flash("Access denied. Veterans only.", "error")
        return redirect(url_for("main.index"))

    profile = VeteranProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or not profile.is_verified:
        flash("You must be a verified veteran to use profile boost.", "error")
        return redirect(url_for("dashboard.veteran"))

    boost_fee = PaymentSetting.get_setting("boost_fee", DEFAULT_BOOST_FEE)

    return render_template(
        "payments/veteran_boost.html",
        boost_fee=boost_fee,
        payment_public_key=payment_gateway_service.get_public_key(),
        gateway_name=payment_gateway_service.get_gateway_name(),
    )


@payments_bp.route("/veteran/boost/initialize", methods=["POST"])
@login_required
def initialize_boost_payment():
    if not current_user.is_veteran():
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        boost_fee = PaymentSetting.get_setting("boost_fee", DEFAULT_BOOST_FEE)
        reference = payment_gateway_service.generate_reference("BST")

        payment = Payment(
            user_id=current_user.id,
            reference=reference,
            amount=boost_fee,
            payment_type="boost",
            description="Veteran profile boost for 7 days",
            status="pending",
        )
        db.session.add(payment)
        db.session.flush()

        callback_url = url_for(
            "payments.verify_payment", reference=reference, _external=True
        )
        metadata = {
            "payment_id": payment.id,
            "user_id": current_user.id,
            "payment_type": "boost",
            "user_name": current_user.full_name,
        }

        success, response = payment_gateway_service.initialize_payment(
            email=current_user.email,
            amount=boost_fee,
            reference=reference,
            callback_url=callback_url,
            metadata=metadata,
        )

        if success:
            payment.gateway_reference = response.get("reference") or response.get(
                "tx_ref"
            )
            db.session.commit()
            return jsonify(
                {
                    "success": True,
                    "authorization_url": response.get("authorization_url")
                    or response.get("link"),
                    "reference": reference,
                }
            )
        else:
            db.session.rollback()
            return jsonify(
                {
                    "success": False,
                    "message": response.get("error", "Payment initialization failed"),
                }
            ), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Boost payment initialization error: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500