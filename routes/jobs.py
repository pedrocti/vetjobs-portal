from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import current_user
from models import JobPosting, VeteranProfile
from app import db

jobs_bp = Blueprint('jobs', __name__)

# Public job board route - accessible to all visitors
@jobs_bp.route('/')
@jobs_bp.route('/board')
def job_board():
    """Public job board - accessible to all visitors."""
    
    # Get approved and active job posts
    page = request.args.get('page', 1, type=int)
    per_page = 12  # 12 jobs per page
    
    # Filter options
    location_filter = request.args.get('location', '')
    job_type_filter = request.args.get('job_type', '')
    search_query = request.args.get('search', '')
    
    # Base query for approved and active jobs
    query = JobPosting.query.filter_by(status='approved', is_active=True)
    
    # Apply filters
    if location_filter:
        query = query.filter(JobPosting.location.ilike(f'%{location_filter}%'))

    if job_type_filter:
        query = query.filter_by(job_type=job_type_filter)

    if search_query:
        query = query.filter(
            db.or_(
                JobPosting.title.ilike(f'%{search_query}%'),
                JobPosting.company_name.ilike(f'%{search_query}%'),
                JobPosting.description.ilike(f'%{search_query}%')  # ✅ updated
            )
        )
    
    # Paginate results
    jobs = query.order_by(JobPosting.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get filter options for dropdowns
    locations = db.session.query(JobPosting.location).filter_by(status='approved', is_active=True).distinct().all()
    locations = [loc[0] for loc in locations if loc[0]]
    
    return render_template('jobs/job_board.html', 
                         jobs=jobs, 
                         locations=locations,
                         current_filters={
                             'location': location_filter,
                             'job_type': job_type_filter,
                             'search': search_query
                         })

# Public job details route - accessible to all visitors
@jobs_bp.route('/details/<int:job_id>')
def job_details(job_id):
    """View job details - accessible to all visitors."""

    job = JobPosting.query.get_or_404(job_id)

    # Only show approved and active jobs
    if job.status != 'approved' or not job.is_active:
        flash('Job posting not available.', 'error')
        return redirect(url_for('jobs.job_board'))

    return render_template('jobs/job_details.html', job=job)


@jobs_bp.route('/search')
def search_jobs():
    """Search jobs with AJAX support - accessible to all visitors."""
    
    search_term = request.args.get('q', '').strip()
    
    if not search_term:
        return {'jobs': []}
    
    # Search in job titles and company names
    jobs = JobPosting.query.filter(
        db.and_(
            JobPosting.status == 'approved',
            JobPosting.is_active == True,
            db.or_(
                JobPosting.job_title.ilike(f'%{search_term}%'),
                JobPosting.company_name.ilike(f'%{search_term}%')
            )
        )
    ).limit(10).all()
    
    results = [{
        'id': job.id,
        'title': job.job_title,
        'company': job.company_name,
        'location': job.location,
        'type': job.get_job_type_display()
    } for job in jobs]
    
    return {'jobs': results}