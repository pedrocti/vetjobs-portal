from flask import render_template, flash, redirect, url_for
from flask_login import login_required, current_user
from datetime import datetime
from sqlalchemy import desc

from . import admin_bp
from app import db
from models import JobApplication, JobPosting, User
from .stats import get_admin_stats


@admin_bp.route('/dashboard')
@admin_bp.route('/')
@login_required
def dashboard():
    """Main admin dashboard."""
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('main.index'))

    # ✅ Use centralized stats
    stats = get_admin_stats()

    # =====================
    # 📊 Chart Data
    # =====================
    chart_data = {
        'user_types': {
            'labels': ['Veterans', 'Employers', 'Admins'],
            'data': [
                stats['total_veterans'],
                stats['total_employers'],
                User.query.filter_by(user_type='admin').count()
            ]
        },
        'application_status': {
            'labels': ['Pending', 'Reviewed', 'Accepted', 'Rejected'],
            'data': [
                stats['pending_app_reviews'],
                JobApplication.query.filter_by(status='reviewed').count(),
                stats['accepted_applications'],
                JobApplication.query.filter_by(status='rejected').count()
            ]
        }
    }

    # =====================
    # 🕒 Recent Applications
    # =====================
    recent_applications = db.session.query(
        JobApplication, JobPosting, User
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        User, JobApplication.veteran_id == User.id
    ).order_by(
        desc(JobApplication.created_at)
    ).limit(5).all()

    return render_template(
        'admin/dashboard.html',
        stats=stats,
        chart_data=chart_data,
        recent_applications=recent_applications,
        current_time=datetime.utcnow().strftime("%b %d, %Y %H:%M")
    )