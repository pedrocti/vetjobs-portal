# routes/admin/payment_settings.py

from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user

from . import admin_bp
from app import db
from models import PaymentSetting
from .stats import get_admin_stats


@admin_bp.route('/settings')
@login_required
def payment_settings():
    """Admin payment settings management."""

    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    try:
        # =============================
        # ⚙️ Ensure Defaults Exist
        # =============================
        try:
            PaymentSetting.initialize_defaults(current_user.id)
        except Exception as init_error:
            current_app.logger.warning(f"Default init issue: {init_error}")

        # =============================
        # 📦 Load Settings
        # =============================
        settings = PaymentSetting.query.order_by(
            PaymentSetting.setting_key.asc()
        ).all()

        settings_dict = {}
        for s in settings:
            settings_dict[s.setting_key] = {
                'value': s.setting_value or '',
                'description': s.description or '',
                'type': s.setting_type or 'text',
                'updated_at': s.updated_at
            }

        stats = get_admin_stats()

        return render_template(
            'admin/payment_settings.html',
            settings=settings_dict,
            stats=stats
        )

    except Exception as e:
        current_app.logger.error(f"Error loading payment settings: {e}")
        flash('Error loading payment settings. Please try again.', 'error')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/settings/update', methods=['POST'])
@login_required
def update_payment_settings():
    """Update payment settings."""

    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    try:
        updated_settings = []

        def update_setting(key, label, desc, typ='number'):
            val = request.form.get(key)
            if val is not None and val.strip():
                PaymentSetting.set_setting(
                    key,
                    val.strip(),
                    current_user.id,
                    desc,
                    typ
                )
                updated_settings.append(label)

        # =============================
        # 💰 Core Fees
        # =============================
        update_setting('verification_fee', 'verification fee', 'Fee charged for veteran account verification')
        update_setting('boost_fee', 'boost fee', 'Fee charged for 7-day profile boost')


        # =============================
        # 💰 optimization fee
        # =============================
        update_setting(
            'cv_optimization_fee',
            'cv optimization fee',
            'Professional CV optimization service fee'
        )

        # =============================
        # 🧩 Employer Plans
        # =============================
        update_setting('starter_plan_amount', 'starter plan', 'Monthly fee for Starter plan')
        update_setting('professional_plan_amount', 'professional plan', 'Monthly fee for Professional plan')
        update_setting('enterprise_plus_plan_amount', 'enterprise plus plan', 'Monthly fee for Enterprise Plus plan')

        # =============================
        # 🧩 Training Partner Plans
        # =============================
        update_setting('pro_plan_amount', 'partner pro plan', 'Annual fee for Partner Pro plan')
        update_setting('premium_plan_amount_tp', 'partner premium plan', 'Annual fee for Partner Premium plan')

        # =============================
        # ✨ Feature Fees
        # =============================
        update_setting('resume_fee', 'resume fee', 'AI Resume fee')
        update_setting('review_fee', 'review fee', 'Professional review fee')
        update_setting('ai_flyer_fee', 'AI flyer fee', 'AI Flyer generation fee')

        # =============================
        # 🏦 Payment Gateway
        # =============================
        update_setting('payment_gateway', 'payment gateway', 'Primary gateway', 'text')

        # Paystack
        update_setting('paystack_mode', 'Paystack mode', 'test or live', 'text')
        for mode in ['test', 'live']:
            update_setting(f'paystack_public_key_{mode}', f'Paystack {mode} public key', '', 'text')
            update_setting(f'paystack_secret_key_{mode}', f'Paystack {mode} secret key', '', 'text')

        # Flutterwave
        update_setting('flutterwave_mode', 'Flutterwave mode', 'test or live', 'text')
        for mode in ['test', 'live']:
            update_setting(f'flutterwave_public_key_{mode}', f'Flutterwave {mode} public key', '', 'text')
            update_setting(f'flutterwave_secret_key_{mode}', f'Flutterwave {mode} secret key', '', 'text')

        # =============================
        # ✅ Commit Changes
        # =============================
        db.session.commit()

        if updated_settings:
            current_app.logger.info(f"Payment settings updated: {updated_settings}")
            flash(f'Updated: {", ".join(updated_settings)}', 'success')
        else:
            flash('No changes made.', 'info')

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating payment settings: {e}")
        flash('Error updating settings.', 'error')

    return redirect(url_for('admin.payment_settings'))