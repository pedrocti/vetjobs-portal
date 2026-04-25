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
BASIC_PLAN_AMOUNT = 15000  # ₦15,000/month
PREMIUM_PLAN_AMOUNT = 25000  # ₦25,000/month

# ==============================
#   EMPLOYER SUBSCRIPTION (UPDATED)
# ==============================
@payments_bp.route("/employer/subscription")
@login_required
def employer_subscription_plans():
    """Render employer subscription plans with dynamic pricing and premium tiers."""
    if not current_user.is_employer():
        flash("Access denied. Employers only.", "error")
        return redirect(url_for("main.index"))

    # Lazy imports to avoid circular dependencies
    from models import Subscription, PaymentSetting
    from services.payment_gateway import (
        payment_gateway_service,
    )  # adjust if path differs

    # Get current active subscription
    current_subscription = (
        Subscription.query.filter_by(user_id=current_user.id, status="active")
        .order_by(Subscription.id.desc())
        .first()
    )

    # ✅ Dynamic plan amounts (with safe default fallback)
    starter_amount = PaymentSetting.get_setting("starter_plan_amount", 20000)
    professional_amount = PaymentSetting.get_setting("professional_plan_amount", 40000)
    enterprise_amount = PaymentSetting.get_setting(
        "enterprise_plus_plan_amount", 120000
    )

    # 🧭 Define available plan tiers
    plans = {
        "starter": {
            "name": "Starter",
            "price": starter_amount,
            "description": "For small employers hiring occasionally.",
            "features": [
                "10 Job Postings",
                "Smart Candidate Matching (AI-based)",
                "Access to verified Veterans",
                "Employer Branding Page (logo, story, testimonials)",
                "Monthly Job Promotion on Vetjobportal social media",
                "Standard Email & Chat Support",
            ],
        },
        "professional": {
            "name": "Professional",
            "price": professional_amount,
            "description": "For active recruiters and agencies seeking visibility and analytics.",
            "features": [
                "Unlimited Job Postings",
                "AI Talent Suggestions & Similar Veterans",
                "Featured Employer Badge on homepage",
                "Advanced Analytics (views, applications, veteran match score)",
                "Bulk Messaging to Candidates",
                "Premium Email + WhatsApp Support",
                "2x Monthly Job Boosts",
            ],
        },
        "enterprise_plus": {
            "name": "Enterprise Plus",
            "price": enterprise_amount,
            "description": "For large organizations or strategic partners needing integrations & support.",
            "features": [
                "Everything in Professional",
                "Dedicated Account Manager",
                "Custom Integrations (HR tools, ATS, CRM)",
                "API Access",
                "Team Accounts (multiple recruiters)",
                "Onboarding & Training for HR team",
                "Quarterly Hiring Report + Talent Insights",
                "White-label Employer Portal",
                "Co-branded Sponsorship/CSR Opportunities",
            ],
        },
    }

    # ✅ Render subscription page with payment gateway details
    return render_template(
        "payments/subscription_plans.html",
        plans=plans,
        current_subscription=current_subscription,
        payment_public_key=getattr(
            payment_gateway_service, "get_public_key", lambda: None
        )(),
        gateway_name=getattr(
            payment_gateway_service, "get_gateway_name", lambda: "default"
        )(),
    )


@payments_bp.route("/employer/subscription/initialize", methods=["POST"])
@login_required
def initialize_subscription_payment():
    """Initialize payment for employer subscription with billing + discount support."""

    if not current_user.is_employer():
        return jsonify({"success": False, "message": "Access denied"}), 403

    try:
        data = request.get_json() or {}

        plan_type = data.get("plan_type")
        billing_cycle = data.get("billing_cycle", "monthly")

        valid_plans = ["starter", "professional", "enterprise_plus"]
        valid_cycles = ["monthly", "6_months", "yearly"]

        if plan_type not in valid_plans:
            return jsonify({"success": False, "message": "Invalid plan type"}), 400

        if billing_cycle not in valid_cycles:
            billing_cycle = "monthly"  # fallback safe

        # ✅ Base plan prices
        plan_prices = {
            "starter": PaymentSetting.get_setting("starter_plan_amount", 20000),
            "professional": PaymentSetting.get_setting(
                "professional_plan_amount", 40000
            ),
            "enterprise_plus": PaymentSetting.get_setting(
                "enterprise_plus_plan_amount", 120000
            ),
        }

        base_amount = float(plan_prices.get(plan_type, 20000))

        # ✅ Billing duration (in months)
        duration_map = {"monthly": 1, "6_months": 6, "yearly": 12}

        # ✅ Discounts
        discount_map = {"monthly": 0, "6_months": 0.10, "yearly": 0.20}

        months = duration_map[billing_cycle]
        discount = discount_map[billing_cycle]

        # ✅ FINAL AMOUNT
        amount = base_amount * months * (1 - discount)

        # Ensure integer (Paystack/Flutterwave safe)
        amount = int(amount)

        reference = payment_gateway_service.generate_reference("SUB")

        # ✅ Store EVERYTHING needed later
        payment_metadata = {
            "plan_type": plan_type,
            "billing_cycle": billing_cycle,
            "months": months,
            "discount": discount,
            "base_amount": base_amount,
            "user_id": current_user.id,
        }

        payment = Payment(
            user_id=current_user.id,
            reference=reference,
            amount=amount,
            payment_type="subscription",
            description=f"{plan_type.replace('_', ' ').title()} ({billing_cycle}) subscription",
            status="pending",
            payment_metadata=payment_metadata,
        )

        db.session.add(payment)
        db.session.flush()

        callback_url = url_for(
            "payments.verify_payment", reference=reference, _external=True
        )

        metadata = {
            "payment_id": payment.id,
            "user_id": current_user.id,
            "payment_type": "subscription",
            "plan_type": plan_type,
            "billing_cycle": billing_cycle,
            "user_name": current_user.full_name,
        }

        success, response = payment_gateway_service.initialize_payment(
            email=current_user.email,
            amount=amount,
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
        current_app.logger.error(f"Subscription payment initialization error: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 500