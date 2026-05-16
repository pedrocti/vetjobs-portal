from flask import (
    Blueprint, render_template, request, flash,
    redirect, url_for, current_app, jsonify,
)
from flask_login import login_required, current_user
from models import Payment, Subscription, PaymentSetting, VeteranProfile, User
from app import db
from services.notification_service import notification_service
from services.payment_gateway import payment_gateway_service
from datetime import datetime, timedelta
import json
from . import payments_bp

BASIC_PLAN_AMOUNT   = 15000
PREMIUM_PLAN_AMOUNT = 25000


@payments_bp.route("/employer/subscription")
@login_required
def employer_subscription_plans():
    if not current_user.is_employer():
        flash("Access denied. Employers only.", "error")
        return redirect(url_for("main.index"))

    from models.subscription import Subscription as Sub

    current_subscription = (
        Subscription.query.filter_by(user_id=current_user.id, status="active")
        .order_by(Subscription.id.desc())
        .first()
    )

    starter_amount      = PaymentSetting.get_setting("starter_plan_amount",        Sub.get_plan_features("starter")["amount"])
    professional_amount = PaymentSetting.get_setting("professional_plan_amount",    Sub.get_plan_features("professional")["amount"])
    enterprise_amount   = PaymentSetting.get_setting("enterprise_plus_plan_amount", Sub.get_plan_features("enterprise_plus")["amount"])

    plans = {
        "starter": {
            "name": "Starter",
            "price": starter_amount,
            "description": "For employers starting to explore veteran talent.",
            "features": [
                "3 Active Job Postings",
                "Browse & view verified veteran profiles",
                "View candidate CVs online (no download)",
                "Application email notifications",
                "Standard email support",
            ],
            "not_included": [
                "CV downloads",
                "Direct messaging with veterans",
                "Analytics",
                "Job boosts",
            ],
        },
        "professional": {
            "name": "Professional",
            "price": professional_amount,
            "description": "For active hiring teams that need full platform access.",
            "features": [
                "Unlimited Job Postings",
                "Browse, view & download veteran CVs",
                "Direct messaging with veterans",
                "2 Job boosts per month",
                "Priority email & WhatsApp support",
            ],
            "not_included": [
                "Team accounts",
                "Dedicated account manager",
                "API access",
            ],
        },
        "enterprise_plus": {
            "name": "Enterprise Plus",
            "price": enterprise_amount,
            "description": "For large organisations with strategic hiring needs.",
            "features": [
                "Everything in Professional",
                "Team accounts — multiple recruiters",
                "Dedicated account manager",
                "5 Job boosts per month",
                "Priority onboarding support",
                "Quarterly talent insights report",
                "API access for HR tool integration",
            ],
            "not_included": [],
        },
    }

    return render_template(
        "payments/subscription_plans.html",
        plans=plans,
        current_subscription=current_subscription,
        payment_public_key=payment_gateway_service.get_public_key(),
        gateway_name=payment_gateway_service.get_gateway_name(),
    )


@payments_bp.route("/employer/subscription/initialize", methods=["POST"])
@login_required
def initialize_employer_subscription():
    if not current_user.is_employer():
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        data         = request.get_json() or {}
        plan_type    = data.get("plan_type", "starter")
        billing_cycle = data.get("billing_cycle", "monthly")

        from models.subscription import Subscription as Sub
        features     = Sub.get_plan_features(plan_type)
        base_amount  = PaymentSetting.get_setting(
            f"{plan_type}_plan_amount", features["amount"]
        )

        discount_map = {"monthly": 0, "6_months": 0.10, "yearly": 0.20}
        duration_map = {"monthly": 30, "6_months": 182, "yearly": 365}
        discount     = discount_map.get(billing_cycle, 0)
        final_amount = int(base_amount * (1 - discount))

        reference = payment_gateway_service.generate_reference("SUB")

        payment = Payment(
            user_id=current_user.id,
            reference=reference,
            amount=final_amount,
            payment_type="subscription",
            description=f"{features['name']} — {billing_cycle.replace('_',' ')}",
            status="pending",
        )
        db.session.add(payment)
        db.session.flush()

        callback_url = url_for(
            "payments.verify_payment", reference=reference, _external=True
        )
        metadata = {
            "payment_id":   payment.id,
            "user_id":      current_user.id,
            "payment_type": "subscription",
            "plan_type":    plan_type,
            "billing_cycle": billing_cycle,
            "user_name":    current_user.full_name,
        }

        # Save metadata to payment record so verification can read it
        payment.payment_metadata = metadata
        db.session.flush()

        success, response = payment_gateway_service.initialize_payment(
            email=current_user.email,
            amount=final_amount,
            reference=reference,
            callback_url=callback_url,
            metadata=metadata,
        )

        if success:
            payment.gateway_reference = response.get("reference") or response.get("tx_ref")
            db.session.commit()
            return jsonify({
                "success": True,
                "authorization_url": response.get("authorization_url") or response.get("link"),
                "reference": reference,
            })
        else:
            db.session.rollback()
            return jsonify({
                "success": False,
                "message": response.get("error", "Payment initialization failed"),
            }), 400

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Subscription payment error: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
