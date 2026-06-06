"""
routes/applications/smart_apply.py
------------------------------------
Smart apply flow for VetJobPortal.

Handles two job types:

1. ADMIN-POSTED JOBS (is_admin_posted=True):
   Step 1 — POST /jobs/<id>/check-cv
            Scans veteran's CV against job requirements.
            Returns JSON: {match, score, reasoning, matched_skills, missing_skills}

   Step 2a — If email job: POST /jobs/<id>/submit-application
             Sends CV via Brevo transactional email to employer's apply_email.
             Returns JSON: {success, message}

   Step 2b — If link job: GET redirect to external_apply_url
             (frontend handles this after a successful CV check)

2. EMPLOYER-POSTED JOBS (is_admin_posted=False):
   Step 1 — Same CV check (optional but prompted)
   Step 2 — Normal in-platform application (existing flow unchanged)
"""

import os
import logging
from datetime import datetime

import requests as http_requests
from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user

logger = logging.getLogger(__name__)

smart_apply_bp = Blueprint('smart_apply', __name__, url_prefix='/jobs')


def _get_veteran_profile():
    """Get the current user's veteran profile, or None."""
    from models import VeteranProfile
    return VeteranProfile.query.filter_by(user_id=current_user.id).first()


def _get_cv_path(profile) -> str | None:
    """Resolve the absolute path to the veteran's CV file."""
    if not profile or not profile.resume_file:
        return None
    resume = profile.resume_file
    if os.path.isabs(resume) and os.path.exists(resume):
        return resume
    # Try all possible upload locations
    root = current_app.root_path
    candidates = [
        os.path.join(root, 'static', 'uploads', 'resumes', resume.lstrip('/')),
        os.path.join(root, 'static', 'uploads', resume.lstrip('/')),
        os.path.join(root, resume.lstrip('/')),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None


# ─────────────────────────────────────────────────────────────
# STEP 1 — CV MATCH CHECK
# POST /jobs/<job_id>/check-cv
# ─────────────────────────────────────────────────────────────

@smart_apply_bp.route('/<int:job_id>/check-cv', methods=['POST'])
@login_required
def check_cv(job_id):
    from models.jobpost import JobPosting
    from services.cv_scanner import scan_cv_against_job

    job = JobPosting.query.get_or_404(job_id)

    if current_user.user_type != 'veteran':
        return jsonify({'error': 'Only veterans can apply for jobs.'}), 403

    profile = _get_veteran_profile()
    if not profile:
        return jsonify({
            'error': 'no_profile',
            'message': 'Please complete your veteran profile before applying.'
        }), 400

    cv_path = _get_cv_path(profile)
    if not cv_path:
        return jsonify({
            'error': 'no_cv',
            'message': 'You have not uploaded a CV yet. Please upload your CV in your profile before applying.',
            'action_url': '/dashboard/profile'
        }), 400

    result = scan_cv_against_job(
        resume_file_path=cv_path,
        job_title=job.title,
        job_requirements=job.requirements,
        job_description=job.description,
    )

    if result.get('error') == 'cv_unreadable':
        return jsonify({
            'error': 'cv_unreadable',
            'message': 'We could not read your CV. Please ensure it is a valid PDF or Word document.',
            'action_url': '/dashboard/profile'
        }), 400

    # Determine apply method for the frontend
    apply_method = None
    if job.is_admin_posted:
        if job.apply_email:
            apply_method = 'email'
        elif job.external_apply_url:
            apply_method = 'link'

    return jsonify({
        'score':          result['score'],
        'is_match':       result['is_match'],
        'reasoning':      result['reasoning'],
        'matched_skills': result.get('matched_skills', []),
        'missing_skills': result.get('missing_skills', []),
        'apply_method':   apply_method,
        'apply_url':      job.external_apply_url if apply_method == 'link' else None,
        'job_title':      job.title,
        'company_name':   job.company_name,
    })


# ─────────────────────────────────────────────────────────────
# STEP 2A — SUBMIT APPLICATION VIA BREVO EMAIL
# POST /jobs/<job_id>/submit-application
# For admin-posted email jobs only.
# ─────────────────────────────────────────────────────────────

@smart_apply_bp.route('/<int:job_id>/submit-application', methods=['POST'])
@login_required
def submit_application(job_id):
    from models.jobpost import JobPosting
    from extensions import db

    job = JobPosting.query.get_or_404(job_id)

    if current_user.user_type != 'veteran':
        return jsonify({'error': 'Only veterans can apply.'}), 403

    if not job.is_admin_posted or not job.apply_email:
        return jsonify({'error': 'This job does not use email application.'}), 400

    profile = _get_veteran_profile()
    if not profile:
        return jsonify({'error': 'Veteran profile not found.'}), 400

    cv_path = _get_cv_path(profile)
    if not cv_path:
        return jsonify({
            'error': 'no_cv',
            'message': 'Please upload your CV before applying.'
        }), 400

    # Build veteran's full name
    veteran_name = current_user.full_name or current_user.email.split('@')[0]
    veteran_email = current_user.email
    veteran_phone = getattr(profile, 'phone', '') or ''

    # Send via Brevo
    success, message = _send_application_via_brevo(
        job=job,
        veteran_name=veteran_name,
        veteran_email=veteran_email,
        veteran_phone=veteran_phone,
        cv_path=cv_path,
    )

    if success:
        # Log the application in DB + send notifications
        try:
            from models import JobApplication
            existing = JobApplication.query.filter_by(
                job_id=job_id, veteran_id=current_user.id
            ).first()
            if not existing:
                app_record = JobApplication(
                    job_id=job_id,
                    veteran_id=current_user.id,
                    status='submitted',
                    applied_at=datetime.utcnow(),
                    cover_letter=f"Application submitted via VetJobPortal on behalf of {veteran_name}.",
                )
                db.session.add(app_record)
                db.session.commit()

            # In-platform notification to veteran
            try:
                from services.notification_service import NotificationService
                ns = NotificationService()
                ns.notify_application_status_change(
                    user_id=current_user.id,
                    job_title=job.title,
                    status='submitted',
                    employer_message=(
                        f"Your CV has been sent to {job.company_name} on your behalf "
                        f"by VetJobPortal. We wish you the best of luck!"
                    )
                )
            except Exception as e:
                logger.warning(f"[smart_apply] Notification failed: {e}")

            # Confirmation email to veteran via Brevo
            try:
                from services.brevo_service import BrevoService
                brevo = BrevoService()
                brevo._request('POST', 'https://api.brevo.com/v3/smtp/email', json={
                    "sender": {"name": "VetJobPortal", "email": "support@vetjobportal.com"},
                    "to": [{"email": veteran_email, "name": veteran_name}],
                    "subject": f"Application Submitted — {job.title} at {job.company_name}",
                    "htmlContent": f"""
                    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
                      <div style="background:#0d2137;padding:24px;text-align:center;">
                        <h2 style="color:#d4af37;margin:0;">Application Submitted ✅</h2>
                      </div>
                      <div style="padding:24px;background:#f9f9f9;">
                        <p>Dear <strong>{veteran_name}</strong>,</p>
                        <p>Your application for <strong>{job.title}</strong> at
                        <strong>{job.company_name}</strong> has been successfully submitted
                        on your behalf by VetJobPortal.</p>
                        <div style="background:#fff;border-left:4px solid #d4af37;padding:16px;margin:20px 0;">
                          <p style="margin:0;"><strong>Job:</strong> {job.title}</p>
                          <p style="margin:8px 0 0;"><strong>Company:</strong> {job.company_name}</p>
                          <p style="margin:8px 0 0;"><strong>Location:</strong> {job.location}</p>
                          <p style="margin:8px 0 0;"><strong>Applied:</strong> {datetime.utcnow().strftime('%d %b %Y')}</p>
                        </div>
                        <p>Your CV was sent professionally on your behalf. If the employer
                        is interested, they will contact you directly at <strong>{veteran_email}</strong>.</p>
                        <p>Keep applying to more roles on VetJobPortal to maximise your chances.</p>
                        <p style="color:#888;font-size:12px;margin-top:32px;">
                          VetJobPortal — Nigeria's #1 platform for military veteran employment
                        </p>
                      </div>
                    </div>
                    """
                })
            except Exception as e:
                logger.warning(f"[smart_apply] Confirmation email failed: {e}")

        except Exception as e:
            logger.warning(f"[smart_apply] Could not log application: {e}")

        return jsonify({
            'success': True,
            'message': f'Your application has been submitted to {job.company_name} on your behalf. A confirmation has been sent to {veteran_email}. Good luck!'
        })
    else:
        return jsonify({'success': False, 'message': message}), 500


def _send_application_via_brevo(job, veteran_name, veteran_email, veteran_phone, cv_path):
    """
    Send the veteran's CV to the employer via Brevo.
    - Sender name = veteran's name (looks like it came from the applicant)
    - Reply-To = veteran's email (employer replies directly to them)
    - Subject = extracted from how_to_apply or professionally composed
    - CV renamed professionally
    - Body written in first person as if veteran wrote it
    """
    import base64, re as _re

    api_key = os.environ.get('BREVO_API_KEY') or os.environ.get('SENDINBLUE_API_KEY')
    if not api_key:
        logger.error("[smart_apply] No Brevo API key configured")
        return False, "Email service not configured. Please contact support."

    # Read and encode CV
    try:
        with open(cv_path, 'rb') as f:
            cv_bytes = f.read()
        cv_base64 = base64.b64encode(cv_bytes).decode('utf-8')
        # Professional filename: FirstName_LastName_CV.pdf
        name_parts = veteran_name.strip().split()
        clean_name = '_'.join(p.capitalize() for p in name_parts if p)
        ext = os.path.splitext(cv_path)[1].lower() or '.pdf'
        cv_filename = f"{clean_name}_CV{ext}"
    except Exception as e:
        logger.error(f"[smart_apply] Could not read CV: {e}")
        return False, "Could not read your CV file. Please re-upload it in your profile."

    # ── Build subject line ───────────────────────────────────
    # Check if employer specified a subject format in how_to_apply
    subject = None
    how_to_apply = job.how_to_apply or ''

    subject_patterns = [
        r'subject[:\s]+[\x22\x27]?([^\x22\x27\n]{5,80})[\x22\x27]?',
        r'title[:\s]+[\x22\x27]?([^\x22\x27\n]{5,80})[\x22\x27]?',
        r'e-?mail\s+subject[:\s]+[\x22\x27]?([^\x22\x27\n]{5,80})[\x22\x27]?',
    ]
    for pat in subject_patterns:
        m = _re.search(pat, how_to_apply, _re.IGNORECASE)
        if m:
            # Fill in the veteran's name and job title placeholders
            subject = m.group(1).strip()
            subject = subject.replace('[Name]', veteran_name)
            subject = subject.replace('[name]', veteran_name)
            subject = subject.replace('[Position]', job.title)
            subject = subject.replace('[position]', job.title)
            break

    # Default professional subject if none specified
    if not subject:
        # Extract clean job title (remove company name if appended)
        clean_title = job.title.split(' at ')[0].strip() if ' at ' in job.title else job.title
        subject = f"Application for {clean_title} — {veteran_name}"

    # ── Build email body ─────────────────────────────────────
    # Written in first person as if veteran sent it directly
    phone_line = f"<li><strong>Phone:</strong> {veteran_phone}</li>" if veteran_phone else ""

    # Extract any specific instructions from how_to_apply
    instructions = ''
    if how_to_apply and len(how_to_apply) > 20:
        # Clean up and include relevant instructions
        clean_instructions = how_to_apply.strip()
        # Remove the email address line since we're already emailing
        clean_instructions = _re.sub(
            r'(?:send|email|forward)\s+(?:your\s+)?(?:cv|resume)\s+to[:\s]+\S+@\S+',
            '', clean_instructions, flags=_re.IGNORECASE
        ).strip()
        if len(clean_instructions) > 20:
            instructions = f"""
            <div style="background:#f5f5f5;border-left:3px solid #ccc;padding:12px 16px;margin:16px 0;font-size:13px;color:#555;">
              <strong>Application Instructions:</strong><br>{clean_instructions}
            </div>"""

    clean_job_title = job.title.split(' at ')[0].strip() if ' at ' in job.title else job.title
    company = job.company_name if job.company_name != 'Employer (via VetJobPortal)' else 'your organisation'

    html_body = f"""
<div style="font-family:Arial,sans-serif;max-width:680px;margin:0 auto;color:#333;line-height:1.7;">

  <p>Dear Hiring Manager,</p>

  <p>
    I am writing to apply for the position of <strong>{clean_job_title}</strong>
    advertised at {company}. Having served in the Nigerian military, I bring a strong
    foundation of discipline, leadership, and operational expertise that I believe
    aligns closely with the requirements of this role.
  </p>

  <p>
    Please find attached my CV for your consideration. I am confident that my
    background and experience make me a strong candidate for this position, and I
    would welcome the opportunity to discuss how I can contribute to your team.
  </p>

  {instructions}

  <p><strong>My Contact Details:</strong></p>
  <ul style="padding-left:20px;">
    <li><strong>Name:</strong> {veteran_name}</li>
    <li><strong>Email:</strong> {veteran_email}</li>
    {phone_line}
  </ul>

  <p>
    I am available for an interview at your earliest convenience and can be
    reached directly at <a href="mailto:{veteran_email}">{veteran_email}</a>.
  </p>

  <p>Thank you for your time and consideration. I look forward to hearing from you.</p>

  <p>
    Yours faithfully,<br>
    <strong>{veteran_name}</strong>
  </p>

  <hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
  <p style="font-size:11px;color:#aaa;text-align:center;">
    This application was facilitated by
    <a href="https://vetjobportal.com" style="color:#aaa;">VetJobPortal.com</a>
    — Nigeria's #1 platform connecting military veterans with civilian employers.<br>
    To respond to the applicant, please reply directly to
    <a href="mailto:{veteran_email}" style="color:#aaa;">{veteran_email}</a>.
  </p>
</div>
"""

    text_body = f"""Dear Hiring Manager,

I am writing to apply for the position of {clean_job_title} advertised at {company}.

Having served in the Nigerian military, I bring discipline, leadership, and operational
experience that aligns with this role. Please find my CV attached.

Name: {veteran_name}
Email: {veteran_email}
{"Phone: " + veteran_phone if veteran_phone else ""}

I am available for interview at your earliest convenience.

Yours faithfully,
{veteran_name}

---
Application facilitated by VetJobPortal.com
Reply directly to: {veteran_email}
"""

    payload = {
        "sender": {
            "name": veteran_name,
            "email": "support@vetjobportal.com",
        },
        "to": [{"email": job.apply_email, "name": "Hiring Manager"}],
        "replyTo": {"email": veteran_email, "name": veteran_name},
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
        "attachment": [{
            "content": cv_base64,
            "name": cv_filename,
        }],
    }

    try:
        response = http_requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "content-type": "application/json",
                "api-key": api_key,
            },
            json=payload,
            timeout=15,
        )
        if response.status_code in (200, 201):
            logger.info(
                f"[smart_apply] Application sent: {veteran_name} → {job.apply_email} "
                f"| Subject: {subject} | CV: {cv_filename}"
            )
            return True, "Application submitted successfully."
        else:
            logger.error(f"[smart_apply] Brevo error {response.status_code}: {response.text}")
            return False, "Failed to send application. Please try again or contact support."
    except Exception as e:
        logger.error(f"[smart_apply] Email send exception: {e}")
        return False, "A network error occurred. Please try again."

