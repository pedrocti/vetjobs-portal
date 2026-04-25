import re
from datetime import datetime
from models import EmployerProfile
from app import db


def sanitize_input(value, max_length=255):
    """Basic input sanitizer to prevent HTML/script injection."""
    if not value:
        return ""
    clean = re.sub(r"<[^>]*>", "", value)
    return clean.strip()[:max_length]


def validate_email(email):
    """Basic email format check."""
    if not email:
        return False
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)


def validate_phone(phone):
    """Basic phone number validation (digits, +, -, and spaces)."""
    if not phone:
        return False
    return re.match(r"^[0-9+\-\s]+$", phone)


def get_or_create_employer_profile(user_id):
    """Return an existing employer profile or create a new one."""
    profile = EmployerProfile.query.filter_by(user_id=user_id).first()

    if not profile:
        profile = EmployerProfile(user_id=user_id, created_at=datetime.utcnow())
        db.session.add(profile)
        db.session.commit()

    return profile


def log_security_event(event_type, user_id, details=None, ip_address=None):
    """
    Lightweight logger for security-related actions (profile updates, logins, etc.).
    """
    try:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] {event_type} | User: {user_id} | IP: {ip_address or 'unknown'} | Details: {details or '{}'}\n"
        with open("security_events.log", "a") as f:
            f.write(log_line)
    except Exception as e:
        # Avoid breaking app flow if logging fails
        print(f"Security log error: {e}")

def get_profile_completion(user):
    """
    Compute profile completion percentage for a user (veteran or employer).
    Returns an integer between 0 and 100.
    """
    total_fields = 0
    completed_fields = 0

    # Basic info
    basic_fields = [user.first_name, user.last_name, user.email]
    total_fields += len(basic_fields)
    completed_fields += sum(1 for f in basic_fields if f)

    # Contact info
    contact_fields = [user.phone, user.location]
    total_fields += len(contact_fields)
    completed_fields += sum(1 for f in contact_fields if f)

    # Bio
    total_fields += 1
    completed_fields += 1 if getattr(user, "bio", None) else 0

    # Veteran-specific fields
    if user.is_veteran():
        veteran_profile = getattr(user, "veteran_profile", None)
        veteran_fields = [
            getattr(veteran_profile, "service_branch", None),
            getattr(veteran_profile, "skills", None)
        ]
        total_fields += len(veteran_fields)
        completed_fields += sum(1 for f in veteran_fields if f)

    # Employer-specific fields
    if user.is_employer():
        employer_profile = getattr(user, "employer_profile", None)
        employer_fields = [
            getattr(employer_profile, "company_name", None),
            getattr(employer_profile, "logo", None)
        ]
        total_fields += len(employer_fields)
        completed_fields += sum(1 for f in employer_fields if f)

    # Avoid division by zero
    if total_fields == 0:
        return 0

    return int((completed_fields / total_fields) * 100)
