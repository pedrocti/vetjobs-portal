from flask import request, jsonify, url_for, current_app, render_template
from models import Payment
from app import db
from services.payment_gateway import payment_gateway_service
from services import email_service
from . import payments_bp


@payments_bp.route("/donate", endpoint="donate_page")
def donate_page():
    return render_template("payments/donate.html")

@payments_bp.route("/donations/initiate", methods=["POST"])
def initiate_donation():
    """Public donation endpoint (no login required)."""
    try:
        data = request.get_json(silent=True) or {}

        # ==============================
        #   INPUT EXTRACTION
        # ==============================
        raw_amount = data.get("amount")
        email = (data.get("email") or "").strip()
        note = (data.get("note") or "").strip()
        donation_type = (data.get("type") or "one-time").strip()
        privacy = (data.get("privacy") or "public").strip()

        # ==============================
        #   VALIDATION
        # ==============================
        if raw_amount is None:
            return jsonify({"message": "Amount is required"}), 400

        try:
            # Safe conversion (avoids type warnings)
            amount_float = float(str(raw_amount))
        except (TypeError, ValueError):
            return jsonify({"message": "Invalid amount"}), 400

        if amount_float <= 0:
            return jsonify({"message": "Amount must be greater than zero"}), 400

        # Optional: enforce minimum donation
        if amount_float < 100:
            return jsonify({"message": "Minimum donation is ₦100"}), 400

        # ✅ Convert to int for gateway compatibility
        amount = int(amount_float)

        # Basic email validation (keep simple to avoid breaking legit users)
        if not email or "@" not in email:
            return jsonify({"message": "Valid email required"}), 400

        # ==============================
        #   CREATE PAYMENT
        # ==============================
        reference = payment_gateway_service.generate_reference("DON")

        payment = Payment(
            user_id=None,  # anonymous donation
            reference=reference,
            amount=amount,
            payment_type="donation",
            description=f"Veteran support donation ({donation_type})",
            status="pending",
            payment_metadata={
                "type": donation_type,
                "privacy": privacy,
                "note": note,
                "email": email,
            },
        )

        db.session.add(payment)
        db.session.flush()  # get payment.id safely

        # ==============================
        #   CALLBACK URL
        # ==============================
        callback_url = url_for(
            "payments.verify_payment",
            reference=reference,
            _external=True,
        )

        metadata = {
            "payment_id": payment.id,
            "payment_type": "donation",
            "email": email,
            "type": donation_type,
        }

        # ==============================
        #   INITIALIZE PAYMENT
        # ==============================
        success, response = payment_gateway_service.initialize_payment(
            email=email or "no-reply@vetjobportal.com",  # fallback safe email
            amount=amount,
            reference=reference,
            callback_url=callback_url,
            metadata=metadata,
        )

        if success:
            try:
                # ==============================
                #   SAVE GATEWAY REFERENCES
                # ==============================
                payment.gateway_reference = (
                    response.get("reference")
                    or response.get("tx_ref")
                    or response.get("id")
                )

                payment.status = "pending"

                db.session.commit()

                # ==============================
                #   EXTRACT PAYMENT URL SAFELY
                # ==============================
                payment_url = (
                    response.get("authorization_url")
                    or response.get("link")
                    or (response.get("data") or {}).get("authorization_url")
                )

                if not payment_url:
                    current_app.logger.error(f"No payment URL returned: {response}")
                    db.session.rollback()
                    return jsonify({"message": "Payment initialization failed"}), 500

                # ==============================
                #   SAFE ASYNC EMAIL TRIGGER (NON-BLOCKING)
                # ==============================
                try:
                    from services.email_service import EmailService
                    email_service = EmailService()

                    # Only send admin notification immediately
                    email_service.send_donation_admin_alert(
                        amount=amount,
                        donor_email=email,
                        note=note,
                        donation_type=donation_type,
                        privacy=privacy,
                        reference=reference
                    )

                except Exception as e:
                    current_app.logger.error(f"Admin donation email failed (non-blocking): {e}")

                # ==============================
                #   RETURN PAYMENT URL
                # ==============================
                return jsonify({"payment_url": payment_url})

            except Exception as e:
                db.session.rollback()
                current_app.logger.exception(f"Payment processing error: {str(e)}")
                return jsonify({"message": "Payment processing failed"}), 500

        else:
            db.session.rollback()

            error_msg = (
                response.get("error")
                or response.get("message")
                or "Payment initialization failed"
            )

            current_app.logger.error(f"Donation init failed: {error_msg}")

            return jsonify({"message": error_msg}), 400

    except Exception as e:
            db.session.rollback()
            current_app.logger.exception(f"Donation error: {str(e)}")
            return jsonify({"message": "Server error"}), 500