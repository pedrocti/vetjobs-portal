"""Search and matching routes for the veteran-employer job portal."""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from models import User, VeteranProfile, JobPosting, SavedVeteran, SavedJob, SearchLog, MatchingScore, EmployerProfile, db
from services.search_service import search_service
from utils.security import require_verified_employer
import uuid

search_bp = Blueprint('search', __name__)

# -------------------------
# Subscription Helper
# -------------------------
def can_search_veterans(user):
    """
    Returns True only for Professional or Enterprise Plus active plans.
    Free and Starter plans can visit the page but cannot search or view profiles.
    Admins always have access.
    """
    if not user:
        return False

    if user.is_admin():
        return True

    from models.subscription import Subscription
    sub = Subscription.get_for_user(user)
    if sub and sub.is_active():
        return sub.plan_type in ('professional', 'enterprise_plus')

    return False


# -------------------------
# Employer Veterans Search
# -------------------------
@search_bp.route('/veterans')
@login_required
@require_verified_employer
def search_veterans():
    if not current_user.is_employer():
        flash('Access denied. Employers only.', 'error')
        return redirect(url_for('main.index'))

    can_search = can_search_veterans(current_user)

    page = request.args.get('page', 1, type=int)
    per_page = 12

    search_results = search_service.search_veterans(
        query_params=request.args,
        current_user_id=current_user.id,
        page=page,
        per_page=per_page
    )

    # Free/Starter: blur results and hide sensitive fields
    if not can_search:
        search_results['results'] = search_results['results'][:4]

        for result in search_results['results']:
            profile = result['profile']

            # Create safe display attributes (DO NOT overwrite DB fields)
            profile.display_bio = (profile.bio[:60] + "...") if profile.bio else None
            profile.display_skills = None
            profile.display_years_of_service = None

    return render_template(
        'search/veterans.html',
        search_results=search_results,
        popular_skills=search_service.get_popular_skills(limit=15),
        popular_locations=search_service.get_popular_locations(limit=10),
        current_filters=request.args,
        can_search=can_search
    )


@search_bp.route('/veterans/api')
@login_required
@require_verified_employer
def api_search_veterans():
    if not current_user.is_employer():
        return jsonify({'error': 'Access denied'}), 403

    page = request.args.get('page', 1, type=int)
    per_page = 12

    search_results = search_service.search_veterans(
        query_params=request.args,
        current_user_id=current_user.id,
        page=page,
        per_page=per_page
    )

    access = can_search_veterans(current_user)

    results = search_results['results']
    if not access:
        results = results[:4]

    results_json = []

    for result in results:
        user = result['user']
        profile = result['profile']

        results_json.append({
            'id': user.id,
            'name': user.full_name,
            'location': profile.location or user.location,
            'skills': profile.skills if access else None,
            'years_of_service': profile.years_of_service if access else None,
            'military_branch': profile.military_branch,
            'rank': profile.rank,
            'bio': (
                profile.bio[:200] + '...' if access
                else (profile.bio[:60] + '...' if profile.bio else None)
            ),
            'is_verified': profile.is_verified,
            'is_boosted': result['is_boosted'],
            'is_saved': result['is_saved'],
            'seeking_employment': profile.seeking_employment,
            'profile_url': url_for('veteran.public_profile', user_id=user.id) if access else None
        })

    return jsonify({
        'results': results_json,
        'total_count': search_results['total_count'],
        'page': search_results['page'],
        'total_pages': search_results['total_pages']
    })


# -------------------------
# Save Veteran (LOCKED)
# -------------------------
@search_bp.route('/save-veteran/<int:veteran_id>', methods=['POST'])
@login_required
def save_veteran(veteran_id):
    if not current_user.is_employer():
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    if not can_search_veterans(current_user):
        return jsonify({
            'success': False,
            'message': 'Upgrade to Professional or Enterprise Plus to save veterans.'
        }), 403

    try:
        existing = SavedVeteran.query.filter_by(
            employer_id=current_user.id,
            veteran_id=veteran_id
        ).first()

        if existing:
            return jsonify({'success': False, 'message': 'Veteran already saved'})

        notes = request.json.get('notes', '') if request.is_json else ''

        saved_veteran = SavedVeteran(
            employer_id=current_user.id,
            veteran_id=veteran_id,
            notes=notes
        )

        db.session.add(saved_veteran)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Veteran saved'})

    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Error saving veteran'}), 500


# -------------------------
# Suggestions (LOCKED)
# -------------------------
@search_bp.route('/suggestions/veterans')
@login_required
def suggested_veterans():
    if not current_user.is_employer():
        return jsonify({'error': 'Access denied'}), 403

    if not can_search_veterans(current_user):
        return jsonify({'suggestions': []})

    suggestions = search_service.get_suggested_veterans_for_employer(
        employer_id=current_user.id,
        limit=10
    )

    results = []
    for suggestion in suggestions:
        user = suggestion['user']
        profile = suggestion['profile']

        results.append({
            'id': user.id,
            'name': user.full_name,
            'location': profile.location or user.location,
            'skills': profile.skills,
            'years_of_service': profile.years_of_service,
            'military_branch': profile.military_branch,
            'is_verified': profile.is_verified,
            'match_score': suggestion['match_score'],
            'matching_skills': suggestion['matching_skills'],
            'profile_url': url_for('veteran.public_profile', user_id=user.id)
        })

    return jsonify({'suggestions': results})


# -------------------------
# Session Tracking
# -------------------------
@search_bp.before_request
def ensure_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

@search_bp.route('/autocomplete/skills')
def autocomplete_skills():
    """Autocomplete endpoint for skills."""
    query = request.args.get('q', '').strip().lower()
    
    if len(query) < 2:
        return jsonify([])
    
    popular_skills = search_service.get_popular_skills(limit=50)
    matching_skills = [skill for skill in popular_skills if query in skill.lower()]
    
    return jsonify(matching_skills[:10])

@search_bp.route('/autocomplete/locations')
def autocomplete_locations():
    """Autocomplete endpoint for locations."""
    query = request.args.get('q', '').strip().lower()
    
    if len(query) < 2:
        return jsonify([])
    
    popular_locations = search_service.get_popular_locations(limit=50)
    matching_locations = [location for location in popular_locations if query in location.lower()]
    
    return jsonify(matching_locations[:10])

# Initialize session ID for anonymous tracking
@search_bp.before_request
def ensure_session_id():
    """Ensure each session has a unique ID for analytics."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())


# -------------------------
# Suggested Jobs for Veterans (NEW)
# -------------------------
@search_bp.route('/suggestions/jobs')
@login_required
def suggested_jobs():
    if not current_user.is_veteran():
        return jsonify({'error': 'Access denied'}), 403

    from services.search_service import search_service

    recommendations = search_service.get_recommended_jobs_for_veteran(
        veteran_id=current_user.id,
        limit=10
    )

    results = []
    for item in recommendations:
        job = item['job']
        employer = item['employer']

        results.append({
            'id': job.id,
            'title': job.title,
            'company_name': employer.company_name if hasattr(employer, 'company_name') else 'Company',
            'location': job.location,
            'job_url': url_for('jobs.job_details', job_id=job.id),
            'apply_url': url_for('jobs.apply_job', job_id=job.id),
            'match_score': item.get('match_score', 0)
        })

    return jsonify({'recommendations': results})