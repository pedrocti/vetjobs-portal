from flask import current_app
from sqlalchemy import func
from datetime import datetime, timedelta

from app import db
from models import (
    User, VeteranProfile,
    JobPosting, JobApplication,
    Payment
)


def get_admin_stats():
    """Centralized admin stats (single source of truth)."""
    try:
        # =====================
        # 👥 Users
        # =====================
        total_veterans = User.query.filter_by(user_type='veteran').count()
        active_veterans = User.query.filter_by(user_type='veteran', active=True).count()

        verified_veterans = db.session.query(User).join(
            VeteranProfile, User.id == VeteranProfile.user_id
        ).filter(
            User.user_type == 'veteran',
            VeteranProfile.is_verified == True
        ).count()

        total_employers = User.query.filter_by(user_type='employer').count()
        active_employers = User.query.filter_by(user_type='employer', active=True).count()

        # =====================
        # 💼 Jobs
        # =====================
        total_job_posts = JobPosting.query.count()
        active_job_posts = JobPosting.query.filter_by(is_active=True, status='approved').count()
        pending_job_approvals = JobPosting.query.filter_by(status='pending').count()

        # =====================
        # 📄 Applications
        # =====================
        total_applications = JobApplication.query.count()
        pending_app_reviews = JobApplication.query.filter_by(status='pending').count()
        accepted_applications = JobApplication.query.filter_by(status='accepted').count()

        # =====================
        # ✅ Verification
        # =====================
        pending_verifications = VeteranProfile.query.filter_by(verification_status='pending').count()

        # =====================
        # 💰 Payments (Core)
        # =====================
        total_revenue = db.session.query(func.sum(Payment.amount)).filter_by(status='success').scalar() or 0
        total_payments = Payment.query.filter_by(status='success').count()

        total_transactions = Payment.query.count()
        pending_payments = Payment.query.filter_by(status='pending').count()

        # =====================
        # 📈 Time Calculations
        # =====================
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        monthly_revenue = db.session.query(func.sum(Payment.amount)).filter(
            Payment.status == 'success',
            Payment.created_at >= thirty_days_ago
        ).scalar() or 0

        # =====================
        # 💳 Revenue Breakdown
        # =====================
        verification_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
            status='success', payment_type='verification'
        ).scalar() or 0

        boost_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
            status='success', payment_type='boost'
        ).scalar() or 0

        subscription_revenue = db.session.query(func.sum(Payment.amount)).filter_by(
            status='success', payment_type='subscription'
        ).scalar() or 0

        # =====================
        # 📈 Last 30 Days Activity
        # =====================
        new_veterans_30d = User.query.filter(
            User.user_type == 'veteran',
            User.created_at >= thirty_days_ago
        ).count()

        new_employers_30d = User.query.filter(
            User.user_type == 'employer',
            User.created_at >= thirty_days_ago
        ).count()

        new_applications_30d = JobApplication.query.filter(
            JobApplication.created_at >= thirty_days_ago
        ).count()

        # =====================
        # 📦 RETURN
        # =====================
        return {
            # 👥 Users
            'total_veterans': total_veterans,
            'active_veterans': active_veterans,
            'verified_veterans': verified_veterans,
            'total_employers': total_employers,
            'active_employers': active_employers,

            # 💼 Jobs
            'total_job_posts': total_job_posts,
            'active_job_posts': active_job_posts,
            'pending_job_approvals': pending_job_approvals,

            # 📄 Applications
            'total_applications': total_applications,
            'pending_app_reviews': pending_app_reviews,
            'accepted_applications': accepted_applications,

            # ✅ Verification
            'pending_verifications': pending_verifications,

            # 💰 Payments (Core)
            'total_revenue': float(total_revenue),
            'total_payments': total_payments,
            'total_transactions': total_transactions,
            'pending_payments': pending_payments,

            # 💳 Revenue Breakdown
            'monthly_revenue': float(monthly_revenue),
            'verification_revenue': float(verification_revenue),
            'boost_revenue': float(boost_revenue),
            'subscription_revenue': float(subscription_revenue),

            # 💸 Current Pricing (SAFE DEFAULTS)
            'current_verification_fee': 5000,
            'current_boost_fee': 2000,
            'current_basic_plan': 10000,
            'current_premium_plan': 25000,

            # 📈 Growth Metrics
            'new_veterans_30d': new_veterans_30d,
            'new_employers_30d': new_employers_30d,
            'new_applications_30d': new_applications_30d,
        }

    except Exception as e:
        current_app.logger.error(f"Error calculating admin stats: {e}")

        # =====================
        # 🛑 SAFE FALLBACK
        # =====================
        return {
            # 👥 Users
            'total_veterans': 0,
            'active_veterans': 0,
            'verified_veterans': 0,
            'total_employers': 0,
            'active_employers': 0,

            # 💼 Jobs
            'total_job_posts': 0,
            'active_job_posts': 0,
            'pending_job_approvals': 0,

            # 📄 Applications
            'total_applications': 0,
            'pending_app_reviews': 0,
            'accepted_applications': 0,

            # ✅ Verification
            'pending_verifications': 0,

            # 💰 Payments
            'total_revenue': 0.0,
            'total_payments': 0,
            'total_transactions': 0,
            'pending_payments': 0,

            # 💳 Revenue Breakdown
            'monthly_revenue': 0.0,
            'verification_revenue': 0.0,
            'boost_revenue': 0.0,
            'subscription_revenue': 0.0,

            # 💸 Pricing Defaults
            'current_verification_fee': 0,
            'current_boost_fee': 0,
            'current_basic_plan': 0,
            'current_premium_plan': 0,

            # 📈 Growth
            'new_veterans_30d': 0,
            'new_employers_30d': 0,
            'new_applications_30d': 0,
        }