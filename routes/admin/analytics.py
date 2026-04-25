from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, case
from datetime import datetime, timedelta
import os
from decimal import Decimal
from models import SearchLog, VeteranProfile, JobPosting
from services.search_service import search_service
from datetime import datetime, timedelta
from sqlalchemy import func, text

from . import admin_bp

# Import shared database and models
from app import db
from models import (
    User, VeteranProfile, EmployerProfile, Partner,
    JobPosting, JobApplication, Payment, Subscription,
    PaymentSetting, EmailSetting, Message, Testimonial
)

# Search Analytics

@admin_bp.route('/search-analytics')
@login_required
def search_analytics():
    """Admin search analytics dashboard."""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    # Time range selection
    days = request.args.get('days', 30, type=int)
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Total search stats
    total_veteran_searches = SearchLog.query.filter(
        SearchLog.search_type == 'veteran',
        SearchLog.created_at >= cutoff_date
    ).count()

    total_job_searches = SearchLog.query.filter(
        SearchLog.search_type == 'job',
        SearchLog.created_at >= cutoff_date
    ).count()

    # Popular search terms
    popular_veteran_terms = SearchLog.get_popular_search_terms('veteran', days, 10)
    popular_job_terms = SearchLog.get_popular_search_terms('job', days, 10)

    # Most searched skills from veteran profiles
    popular_skills = search_service.get_popular_skills(20)

    # Geographic data
    popular_locations = search_service.get_popular_locations(15)

    # Active industries from job posts
    industry_stats = db.session.query(
        JobPosting.industry,
        func.count(JobPosting.id).label('job_count')
    ).filter(
        JobPosting.industry.isnot(None),
        JobPosting.industry != '',
        JobPosting.is_active == True
    ).group_by(JobPosting.industry).order_by(
        func.count(JobPosting.id).desc()
    ).limit(10).all()

    # Search activity by day (last 30 days)
    daily_search_stats = []
    for i in range(29, -1, -1):
        date = datetime.utcnow().date() - timedelta(days=i)
        start_date = datetime.combine(date, datetime.min.time())
        end_date = datetime.combine(date, datetime.max.time())

        veteran_searches = SearchLog.query.filter(
            SearchLog.search_type == 'veteran',
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        ).count()

        job_searches = SearchLog.query.filter(
            SearchLog.search_type == 'job',
            SearchLog.created_at >= start_date,
            SearchLog.created_at <= end_date
        ).count()

        daily_search_stats.append({
            'date': date.strftime('%Y-%m-%d'),
            'veteran_searches': veteran_searches,
            'job_searches': job_searches
        })

    # User engagement stats
    unique_searchers = db.session.query(SearchLog.user_id).filter(
        SearchLog.user_id.isnot(None),
        SearchLog.created_at >= cutoff_date
    ).distinct().count()

    # Conversion rates (searches that led to profile views/applications)
    # This would require additional tracking in a real system
    conversion_stats = {
        'profile_views': 0,  # Placeholder
        'applications': 0,   # Placeholder
        'saved_items': 0     # Placeholder
    }

    return render_template('admin/search_analytics.html',
                         total_veteran_searches=total_veteran_searches,
                         total_job_searches=total_job_searches,
                         popular_veteran_terms=popular_veteran_terms,
                         popular_job_terms=popular_job_terms,
                         popular_skills=popular_skills,
                         popular_locations=popular_locations,
                         industry_stats=industry_stats,
                         daily_search_stats=daily_search_stats,
                         unique_searchers=unique_searchers,
                         conversion_stats=conversion_stats,
                         selected_days=days)