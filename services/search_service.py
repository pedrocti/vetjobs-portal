"""
Search and matching service for the veteran-employer job portal.
Handles veteran search, job discovery, and intelligent matching.
"""

from sqlalchemy import and_, or_, func, text
from flask import request, session
from models import User, VeteranProfile, JobPosting, JobApplication, SavedVeteran, SavedJob, SearchLog, MatchingScore, db
from datetime import datetime, timedelta
import re


class SearchService:
    """Service for handling all search and matching functionality."""
    
    @staticmethod
    def search_veterans(query_params, current_user_id=None, page=1, per_page=20):
        """
        Search for veterans with advanced filtering.
        
        Args:
            query_params: Dict of search parameters
            current_user_id: ID of the searching user
            page: Page number for pagination
            per_page: Results per page
        """
        
        # Base query - join User and VeteranProfile
        base_query = db.session.query(User, VeteranProfile).join(
            VeteranProfile, User.id == VeteranProfile.user_id
        ).filter(
            User.user_type == 'veteran',
            User.active == True
        )
        
        # Extract search parameters
        keywords = query_params.get('keywords', '').strip()
        skills = query_params.getlist('skills') or []
        location = query_params.get('location', '').strip()
        min_experience = query_params.get('min_experience', type=int)
        max_experience = query_params.get('max_experience', type=int)
        verified_only = query_params.get('verified_only', type=bool)
        available_only = query_params.get('available_only', type=bool)
        
        filters_used = {
            'keywords': keywords,
            'skills': skills,
            'location': location,
            'min_experience': min_experience,
            'max_experience': max_experience,
            'verified_only': verified_only,
            'available_only': available_only
        }
        
        # Apply filters
        if keywords:
            # Search in name, bio, and skills
            keyword_filter = or_(
                User.first_name.ilike(f'%{keywords}%'),
                User.last_name.ilike(f'%{keywords}%'),
                VeteranProfile.bio.ilike(f'%{keywords}%'),
                VeteranProfile.skills.ilike(f'%{keywords}%'),
                VeteranProfile.military_branch.ilike(f'%{keywords}%'),
                VeteranProfile.rank.ilike(f'%{keywords}%')
            )
            base_query = base_query.filter(keyword_filter)
        
        if skills:
            # Search for any of the specified skills
            skill_conditions = []
            for skill in skills:
                skill_conditions.append(VeteranProfile.skills.ilike(f'%{skill}%'))
            base_query = base_query.filter(or_(*skill_conditions))
        
        if location:
            location_filter = or_(
                User.location.ilike(f'%{location}%'),
                VeteranProfile.location.ilike(f'%{location}%')
            )
            base_query = base_query.filter(location_filter)
        
        if min_experience is not None:
            base_query = base_query.filter(VeteranProfile.years_of_service >= min_experience)
        
        if max_experience is not None:
            base_query = base_query.filter(VeteranProfile.years_of_service <= max_experience)
        
        if verified_only:
            base_query = base_query.filter(VeteranProfile.is_verified == True)
        
        if available_only:
            base_query = base_query.filter(VeteranProfile.seeking_employment == True)
        
        # Ordering: boosted profiles first, then by verification, then by recent activity
        base_query = base_query.order_by(
            VeteranProfile.profile_boosted_until.desc().nullslast(),
            VeteranProfile.is_verified.desc(),
            User.updated_at.desc()
        )
        
        # Get total count before pagination
        total_count = base_query.count()
        
        # Apply pagination
        results = base_query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Log search activity
        SearchLog.log_search(
            search_type='veteran',
            query_terms=keywords,
            filters_used=filters_used,
            results_count=total_count,
            user_id=current_user_id,
            session_id=session.get('session_id'),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None
        )
        
        # Convert results to searchable format
        search_results = []
        for user, profile in results:
            # Check if this veteran is saved by current user
            is_saved = False
            if current_user_id:
                is_saved = SavedVeteran.is_saved(current_user_id, user.id)
            
            search_results.append({
                'user': user,
                'profile': profile,
                'is_saved': is_saved,
                'is_boosted': profile.profile_boosted_until and profile.profile_boosted_until > datetime.utcnow(),
                'match_score': None  # Will be calculated if needed
            })
        
        return {
            'results': search_results,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'filters_used': filters_used
        }
    
    @staticmethod
    def search_jobs(query_params, current_user_id=None, page=1, per_page=20):
        """
        Search for jobs with advanced filtering.
        
        Args:
            query_params: Dict of search parameters
            current_user_id: ID of the searching user
            page: Page number for pagination
            per_page: Results per page
        """
        
        # Base query - join JobPost with User (employer)
        base_query = db.session.query(JobPosting, User).join(
            User, JobPosting.posted_by == User.id
        ).filter(
            JobPosting.status == 'approved',
            JobPosting.is_active == True,
            JobPosting.created_at > datetime.utcnow() - timedelta(days=90)  # Active within 90 days
        )
        
        # Extract search parameters
        keywords = query_params.get('keywords', '').strip()
        industry = query_params.get('industry', '').strip()
        location = query_params.get('location', '').strip()
        min_salary = query_params.get('min_salary', type=int)
        max_salary = query_params.get('max_salary', type=int)
        job_type = query_params.get('job_type', '').strip()
        remote_option = query_params.get('remote_option')
        experience_level = query_params.get('experience_level', '').strip()
        
        filters_used = {
            'keywords': keywords,
            'industry': industry,
            'location': location,
            'min_salary': min_salary,
            'max_salary': max_salary,
            'job_type': job_type,
            'remote_option': remote_option,
            'experience_level': experience_level
        }
        
        # Apply filters
        if keywords:
            # Search in title, description, and required skills
            keyword_filter = or_(
                JobPosting.title.ilike(f'%{keywords}%'),
                JobPosting.description.ilike(f'%{keywords}%'),
                JobPosting.requirements.ilike(f'%{keywords}%'),
                User.company_name.ilike(f'%{keywords}%')
            )
            base_query = base_query.filter(keyword_filter)
        
        if industry:
            base_query = base_query.filter(JobPosting.industry.ilike(f'%{industry}%'))
        
        if location and location.lower() != 'remote':
            base_query = base_query.filter(JobPosting.location.ilike(f'%{location}%'))
        
        if min_salary is not None:
            base_query = base_query.filter(
                or_(
                    JobPosting.salary_min >= min_salary,
                    JobPosting.salary_max >= min_salary
                )
            )
        
        if max_salary is not None:
            base_query = base_query.filter(
                or_(
                    JobPosting.salary_min <= max_salary,
                    JobPosting.salary_max <= max_salary
                )
            )
        
        if job_type:
            base_query = base_query.filter(JobPosting.job_type.ilike(f'%{job_type}%'))
        
        if remote_option == 'remote_only':
            base_query = base_query.filter(JobPosting.job_type == 'remote')
        elif remote_option == 'no_remote':
            base_query = base_query.filter(JobPosting.job_type != 'remote')
        
        if experience_level:
            base_query = base_query.filter(JobPosting.experience_level.ilike(f'%{experience_level}%'))
        
        # Ordering: featured jobs first, then by posting date
        base_query = base_query.order_by(
            JobPosting.created_at.desc()
        )
        
        # Get total count before pagination
        total_count = base_query.count()
        
        # Apply pagination
        results = base_query.offset((page - 1) * per_page).limit(per_page).all()
        
        # Log search activity
        SearchLog.log_search(
            search_type='job',
            query_terms=keywords,
            filters_used=filters_used,
            results_count=total_count,
            user_id=current_user_id,
            session_id=session.get('session_id'),
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None
        )
        
        # Convert results to searchable format
        search_results = []
        for job, employer in results:
            # Check if this job is saved by current user
            is_saved = False
            if current_user_id:
                is_saved = SavedJob.is_saved(current_user_id, job.id)
            
            # Check if user has already applied
            has_applied = False
            if current_user_id:
                has_applied = JobApplication.query.filter_by(
                    job_id=job.id,
                    veteran_id=current_user_id
                ).first() is not None
            
            search_results.append({
                'job': job,
                'employer': employer,
                'is_saved': is_saved,
                'has_applied': has_applied,
                'match_score': None  # Will be calculated if needed
            })
        
        return {
            'results': search_results,
            'total_count': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page,
            'filters_used': filters_used
        }
    
    @staticmethod
    def get_suggested_veterans_for_employer(employer_id, limit=10):
        """
        Get suggested veterans for an employer based on their active job postings.
        Boosted veteran profiles appear first, then sorted by match score.
        """
        from datetime import datetime

        # Get employer's recent active/approved job postings
        recent_jobs = JobPosting.query.filter_by(
            posted_by=employer_id,
            is_active=True
        ).order_by(JobPosting.created_at.desc()).limit(5).all()

        # Fallback: also try pending/draft jobs so new employers see something
        if not recent_jobs:
            recent_jobs = JobPosting.query.filter_by(
                posted_by=employer_id
            ).order_by(JobPosting.created_at.desc()).limit(5).all()

        if not recent_jobs:
            return []

        # Extract keywords from title + requirements + description
        all_keywords = set()
        for job in recent_jobs:
            for source in [job.title, job.requirements, job.description]:
                if source:
                    words = [w.strip('.,()').lower() for w in source.split() if len(w.strip('.,()')) > 3]
                    all_keywords.update(words)
            if job.requirements:
                for kw in job.requirements.split(','):
                    all_keywords.add(kw.strip().lower())

        # Remove very common words
        stopwords = {'with', 'that', 'have', 'will', 'from', 'this', 'your', 'must',
                     'able', 'work', 'team', 'role', 'year', 'years', 'experience',
                     'skill', 'skills', 'good', 'strong', 'required', 'preferred'}
        all_keywords -= stopwords

        if not all_keywords:
            return []

        # Build skill filter conditions
        skill_conditions = []
        for kw in list(all_keywords)[:30]:  # cap to avoid huge queries
            skill_conditions.append(VeteranProfile.skills.ilike(f'%{kw}%'))
            skill_conditions.append(VeteranProfile.bio.ilike(f'%{kw}%'))

        veterans = db.session.query(User, VeteranProfile).join(
            VeteranProfile, User.id == VeteranProfile.user_id
        ).filter(
            User.user_type == 'veteran',
            User.active == True,
            or_(*skill_conditions)
        ).order_by(
            # Boosted veterans first
            VeteranProfile.profile_boosted_until.desc().nullslast(),
            VeteranProfile.is_verified.desc(),
            User.updated_at.desc()
        ).limit(limit * 3).all()  # fetch extra to account for skips

        top_job = recent_jobs[0]
        suggestions = []

        for user, profile in veterans:
            if SavedVeteran.is_saved(employer_id, user.id):
                continue

            match_score = MatchingScore.update_score(user.id, top_job.id)
            matching_skills = SearchService._get_matching_skills(profile.skills, top_job.requirements)
            is_boosted = bool(profile.profile_boosted_until and profile.profile_boosted_until > datetime.utcnow())

            suggestions.append({
                'user': user,
                'profile': profile,
                'match_score': match_score,
                'matching_skills': matching_skills,
                'is_boosted': is_boosted
            })

            if len(suggestions) >= limit:
                break

        # Sort: boosted first, then by match score
        suggestions.sort(key=lambda x: (not x['is_boosted'], -x['match_score']))

        return suggestions
    
    @staticmethod
    def get_recommended_jobs_for_veteran(veteran_id, limit=10):
        """Get recommended jobs for a veteran based on their profile, with fallback."""

        profile = VeteranProfile.query.filter_by(user_id=veteran_id).first()
        user = User.query.get(veteran_id)

        # Query active jobs in last 90 days
        jobs_query = db.session.query(JobPosting, User).join(
            User, JobPosting.posted_by == User.id
        ).filter(
            JobPosting.status == 'approved',
            JobPosting.is_active == True,
            JobPosting.created_at > datetime.utcnow() - timedelta(days=90)
        )

        # Filter by location if profile exists
        if profile and user and user.location:
            jobs_query = jobs_query.filter(
                or_(
                    JobPosting.location.ilike(f'%{user.location}%'),
                    JobPosting.job_type == 'remote'
                )
            )

        all_jobs = jobs_query.order_by(JobPosting.created_at.desc()).all()
        recommendations = []

        # 🔒 Safe boost check (no crash if profile is None)
        is_boosted = False
        if profile and profile.profile_boosted_until:
            is_boosted = profile.profile_boosted_until > datetime.utcnow()

        if profile:
            for job, employer in all_jobs:
                # Skip already applied jobs
                if JobApplication.query.filter_by(
                    job_id=job.id,
                    veteran_id=veteran_id
                ).first():
                    continue

                # Skip saved jobs
                if SavedJob.is_saved(veteran_id, job.id):
                    continue

                # Safe match score calculation
                try:
                    match_score = MatchingScore.update_score(veteran_id, job.id)
                except Exception:
                    match_score = 0

                recommendations.append({
                    'job': job,
                    'employer': employer,
                    'match_score': match_score or 0,
                    'matching_skills': SearchService._get_matching_skills(
                        profile.skills or '',
                        job.requirements or ''
                    )
                })

        # -------------------------
        # 🔥 Improved Sorting Logic
        # -------------------------
        if recommendations:
            if is_boosted:
                # Boosted users → BEST matches first
                recommendations.sort(
                    key=lambda x: (-x['match_score'], x['job'].created_at)
                )
            else:
                # Normal users → recent jobs first
                recommendations.sort(
                    key=lambda x: x['job'].created_at,
                    reverse=True
                )

        # -------------------------
        # ✅ Fallback (unchanged but safer)
        # -------------------------
        if not recommendations:
            fallback_jobs = all_jobs[:limit]
            recommendations = [{
                'job': job,
                'employer': employer,
                'match_score': 0,
                'matching_skills': []
            } for job, employer in fallback_jobs]

        return recommendations[:limit]

    
    
    @staticmethod
    def _get_matching_skills(veteran_skills, job_skills):
        """Get list of skills that match between veteran and job."""
        if not veteran_skills or not job_skills:
            return []
        
        v_skills = set(skill.strip().lower() for skill in veteran_skills.split(','))
        j_skills = set(skill.strip().lower() for skill in job_skills.split(','))
        
        return list(v_skills.intersection(j_skills))
    
    @staticmethod
    def get_popular_skills(limit=20):
        """Get most popular skills from veteran profiles."""
        profiles = VeteranProfile.query.filter(
            VeteranProfile.skills.isnot(None),
            VeteranProfile.skills != ''
        ).all()
        
        skill_counts = {}
        for profile in profiles:
            skills = [skill.strip().lower() for skill in profile.skills.split(',')]
            for skill in skills:
                if skill:  # Skip empty skills
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
        
        # Sort by frequency
        popular_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [skill for skill, count in popular_skills[:limit]]
    
    @staticmethod
    def get_popular_locations(limit=20):
        """Get most popular locations from users and job posts."""
        # Get locations from users
        user_locations = db.session.query(User.location).filter(
            User.location.isnot(None),
            User.location != ''
        ).all()
        
        # Get locations from job posts
        job_locations = db.session.query(JobPosting.location).filter(
            JobPosting.location.isnot(None),
            JobPosting.location != ''
        ).all()
        
        location_counts = {}
        
        # Count user locations
        for (location,) in user_locations:
            clean_location = location.strip()
            if clean_location:
                location_counts[clean_location] = location_counts.get(clean_location, 0) + 1
        
        # Count job locations
        for (location,) in job_locations:
            clean_location = location.strip()
            if clean_location:
                location_counts[clean_location] = location_counts.get(clean_location, 0) + 1
        
        # Sort by frequency
        popular_locations = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [location for location, count in popular_locations[:limit]]


# Create global instance
search_service = SearchService()