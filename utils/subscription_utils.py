# utils/subscription_utils.py
from datetime import datetime
from models import Subscription, EmployerProfile

def get_employer_features(user):
    """
    Return a dict of effective features for the current employer.
    If user has a Subscription record, use it; otherwise fallback to employer_profile + defaults.
    """
    features = {
        'max_job_posts': 1,
        'can_contact_candidates': False,
        'can_export_resumes': False,
        'priority_support': False,
        'featured_jobs': False,
        'social_promotion': False,
        'analytics_access': False,
        'dedicated_manager': False,
        'api_access': False,
        'job_post_notifications': False,  # email/WhatsApp on new job post
        'plan_type': 'free',
        'subscription_active': False,
        'expires_at': None
    }

    if not user or not hasattr(user, 'subscription') or not user.subscription:
        # fallback: if EmployerProfile has subscription flags, use them
        profile = getattr(user, 'employer_profile', None)
        if profile:
            features['subscription_active'] = bool(profile.subscription_active)
            features['plan_type'] = profile.subscription_plan or features['plan_type']
            features['expires_at'] = profile.subscription_expires_at
        return features

    sub = user.subscription
    # base flags from Subscription model (these fields are named in the model)
    features.update({
        'max_job_posts': sub.max_job_posts,
        'can_contact_candidates': bool(sub.can_contact_candidates),
        'can_export_resumes': bool(sub.can_export_resumes),
        'priority_support': bool(sub.priority_support),
        'featured_jobs': bool(sub.featured_jobs),
        'social_promotion': bool(sub.social_promotion),
        'analytics_access': bool(sub.analytics_access),
        'dedicated_manager': bool(sub.dedicated_manager),
        'api_access': bool(sub.api_access),
        'job_post_notifications': bool(getattr(sub, 'job_post_notifications', False)),
        'plan_type': sub.plan_type,
        'subscription_active': sub.is_active(),
        'expires_at': sub.expires_at
    })
    return features


def can_post_new_job(user):
    """
    Return (allowed: bool, message: str).
    Considers approval status and current active subscription + plan limits.
    """
    if not user.is_employer():
        return False, "Only employers can post jobs."

    if not user.is_employer_approved():
        return False, "Employer account not approved."

    sub = getattr(user, 'subscription', None)
    features = get_employer_features(user)

    if not features['subscription_active']:
        return False, "You need an active subscription to post jobs."

    # fetch current count of ACTIVE job postings
    from models import JobPosting
    current_job_count = JobPosting.query.filter_by(posted_by=user.id, is_active=True).count()

    max_posts = features['max_job_posts']
    if max_posts == -1:
        return True, None  # unlimited
    if current_job_count >= max_posts:
        return False, f"You have reached your plan limit of {max_posts} active job post(s). Please upgrade or deactivate existing posts."

    return True, None
