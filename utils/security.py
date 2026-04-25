"""Security utilities for role-based access control and validation."""

from functools import wraps
from flask import flash, redirect, url_for, request, abort
from flask_login import current_user
import re
import os
from werkzeug.utils import secure_filename


def require_role(allowed_roles):
    """Decorator to enforce role-based access control.
    
    Args:
        allowed_roles (list): List of user types allowed to access the route
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.user_type not in allowed_roles:
                flash('Access denied. You do not have permission to view this page.', 'error')
                return redirect(url_for('main.index'))
            
            if not current_user.active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return redirect(url_for('auth.logout'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_veteran(f):
    """Decorator to require veteran role."""
    return require_role(['veteran'])(f)


def require_employer(f):
    """Decorator to require employer role."""
    return require_role(['employer'])(f)


def require_admin(f):
    """Decorator to require admin role."""
    return require_role(['admin'])(f)


def require_completed_profile(f):
    """Decorator to ensure employer has completed their profile."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if current_user.is_employer():
            # Check if employer profile is completed
            from models import EmployerProfile
            profile = EmployerProfile.query.filter_by(user_id=current_user.id).first()
            if not profile or not profile.profile_completed:
                flash('Please complete your profile before accessing this feature.', 'warning')
                return redirect(url_for('employer.complete_profile'))
        
        return f(*args, **kwargs)
    return decorated_function


def require_verified_employer(f):
    """Decorator to ensure employer profile is verified by admin."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        
        if current_user.is_employer():
            from models import EmployerProfile
            profile = EmployerProfile.query.filter_by(user_id=current_user.id).first()
            
            if not profile or not profile.profile_completed:
                flash('Please complete your profile first.', 'warning')
                return redirect(url_for('employer.complete_profile'))
            
                if profile.verification_status != 'approved':
                    flash('Your company profile must be approved by our admin team before accessing this feature.', 'warning')
                    return redirect(url_for('dashboard.employer'))

        
        return f(*args, **kwargs)
    return decorated_function


def validate_file_upload(file, allowed_extensions=None, max_size_mb=5):
    """Validate file upload for security.
    
    Args:
        file: Uploaded file object
        allowed_extensions: List of allowed file extensions (default: PDF, DOCX, JPG, PNG)
        max_size_mb: Maximum file size in MB
    
    Returns:
        tuple: (is_valid, error_message, secure_filename)
    """
    if allowed_extensions is None:
        allowed_extensions = {'pdf', 'docx', 'doc', 'jpg', 'jpeg', 'png', 'gif'}
    
    if not file or not file.filename:
        return False, 'No file selected', None
    
    # Check file extension
    filename = secure_filename(file.filename)
    if '.' not in filename:
        return False, 'File must have an extension', None
    
    extension = filename.rsplit('.', 1)[1].lower()
    if extension not in allowed_extensions:
        return False, f'Invalid file type. Allowed: {", ".join(allowed_extensions)}', None
    
    # Check file size (approximate check using content length)
    if hasattr(file, 'content_length') and file.content_length:
        if file.content_length > max_size_mb * 1024 * 1024:
            return False, f'File too large. Maximum size: {max_size_mb}MB', None
    
    return True, None, filename


def validate_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone):
    """Validate phone number format."""
    # Remove common separators
    clean_phone = re.sub(r'[^\d+]', '', phone)
    # Allow international format (+234...) or domestic format
    pattern = r'^(\+\d{1,3})?[\d\s\-\(\)]{10,15}$'
    return re.match(pattern, phone) is not None


def validate_password_strength(password):
    """Validate password strength.
    
    Returns:
        tuple: (is_valid, list_of_errors)
    """
    errors = []
    
    if len(password) < 8:
        errors.append('Password must be at least 8 characters long')
    
    if not re.search(r'[A-Z]', password):
        errors.append('Password must contain at least one uppercase letter')
    
    if not re.search(r'[a-z]', password):
        errors.append('Password must contain at least one lowercase letter')
    
    if not re.search(r'\d', password):
        errors.append('Password must contain at least one number')
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        errors.append('Password must contain at least one special character')
    
    return len(errors) == 0, errors


def sanitize_input(text, max_length=None):
    """Sanitize user input to prevent XSS and other attacks."""
    if not text:
        return ''
    
    # Remove dangerous characters
    text = re.sub(r'[<>"\']', '', str(text))
    
    # Limit length if specified
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()


def rate_limit_key(user_id=None, ip_address=None, endpoint=None):
    """Generate a rate limiting key."""
    if user_id:
        return f"user:{user_id}:{endpoint}"
    else:
        return f"ip:{ip_address}:{endpoint}"


def log_security_event(event_type, user_id=None, details=None, ip_address=None):
    """Log security-related events for audit purposes."""
    from datetime import datetime
    from models import SecurityLog, db
    
    try:
        log_entry = SecurityLog()
        log_entry.event_type = event_type
        log_entry.user_id = user_id
        log_entry.details = details or {}
        log_entry.ip_address = ip_address
        log_entry.timestamp = datetime.utcnow()
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        # Don't let logging failures break the application
        print(f"Failed to log security event: {e}")

def require_job_posting_permission(f):
    """Decorator to allow employers to post only 1 free job unless subscribed."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        if current_user.is_employer():
            from models import JobPosting, Subscription

            # Count jobs already posted
            job_count = JobPosting.query.filter_by(posted_by=current_user.id).count()

            # Check if employer has an active subscription
            has_subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()

            if job_count >= 1 and not has_subscription:
                flash('You need an active subscription to post more jobs. Please select a subscription plan.', 'warning')
                return redirect(url_for('subscription.plans'))

        return f(*args, **kwargs)
    return decorated_function
