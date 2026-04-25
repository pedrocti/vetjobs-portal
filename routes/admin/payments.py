# routes/admin/payments.py
from flask import render_template, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, desc
from datetime import datetime, timedelta

from . import admin_bp
from app import db
from models import Payment, PaymentSetting
from .stats import get_admin_stats


@admin_bp.route('/payments')
@login_required
def payments_tracking():
    """Payments dashboard."""

    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    try:
        # =====================
        # 📄 Recent Payments
        # =====================
        payment_objects = Payment.query.order_by(
            desc(Payment.created_at)
        ).limit(50).all()

        payments = []
        type_mapping = {
            'verification': 'Verification Fee',
            'boost': 'Profile Boost',
            'subscription': 'Subscription',
            'feature': 'Premium Feature',
            'partner_plan': 'Partner Plan'
        }

        for p in payment_objects:
            payments.append({
                'id': p.id,
                'user': p.user.full_name if p.user else 'Unknown',
                'type': type_mapping.get(p.payment_type, p.payment_type),
                'amount': float(p.amount or 0),
                'status': (p.status or 'unknown').title(),
                'date': p.created_at,
                'formatted_amount': getattr(p, 'formatted_amount', f"{p.amount or 0}")
            })

        # =====================
        # 💰 Revenue Stats
        # =====================
        total_revenue = db.session.query(func.sum(Payment.amount))\
            .filter_by(status='success').scalar() or 0

        monthly_revenue = db.session.query(func.sum(Payment.amount))\
            .filter(
                Payment.status == 'success',
                Payment.created_at >= datetime.utcnow() - timedelta(days=30)
            ).scalar() or 0

        stats = {
            'total_revenue': float(total_revenue),
            'monthly_revenue': float(monthly_revenue),
            'total_transactions': Payment.query.count(),
            'pending_payments': Payment.query.filter_by(status='pending').count(),

            'verification_revenue': float(
                db.session.query(func.sum(Payment.amount))
                .filter_by(status='success', payment_type='verification')
                .scalar() or 0
            ),

            'boost_revenue': float(
                db.session.query(func.sum(Payment.amount))
                .filter_by(status='success', payment_type='boost')
                .scalar() or 0
            ),

            'subscription_revenue': float(
                db.session.query(func.sum(Payment.amount))
                .filter_by(status='success', payment_type='subscription')
                .scalar() or 0
            ),

            'feature_revenue': float(
                db.session.query(func.sum(Payment.amount))
                .filter_by(status='success', payment_type='feature')
                .scalar() or 0
            ),

            'partner_revenue': float(
                db.session.query(func.sum(Payment.amount))
                .filter_by(status='success', payment_type='partner_plan')
                .scalar() or 0
            ),

            # Current fees (safe fallback)
            'current_verification_fee': float(
                PaymentSetting.get_setting('verification_fee', 2000) or 0
            ),
            'current_boost_fee': float(
                PaymentSetting.get_setting('boost_fee', 1000) or 0
            ),
        }

        # =====================
        # 📊 Merge Admin Stats
        # =====================
        stats.update(get_admin_stats())

        return render_template(
            'admin/payments.html',
            payments=payments,
            stats=stats
        )

    except Exception as e:
        current_app.logger.error(f"Error loading payments dashboard: {e}")
        flash('Error loading payments data.', 'error')
        return redirect(url_for('admin.dashboard'))