# services/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
from services.job_scraper import run_full_scrape

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# JOB 1 — VETERAN PROFILE REMINDER
# Sends to veterans who registered 3+ days ago and still
# haven't completed their profile (onboarding_completed=False)
# ─────────────────────────────────────────────────────────────
def send_veteran_profile_reminders(app):
    with app.app_context():
        try:
            from models import User
            from services.brevo_service import BrevoService

            cutoff = datetime.utcnow() - timedelta(days=3)

            veterans = User.query.filter(
                User.user_type          == "veteran",
                User.is_verified        == True,
                User.onboarding_completed == False,
                User.created_at         <= cutoff
            ).all()

            if not veterans:
                logger.info("[SCHEDULER] No veterans need profile reminder today")
                return

            brevo = BrevoService()
            sent  = 0

            for user in veterans:
                try:
                    success = brevo.send_profile_reminder_email(user)
                    if success:
                        sent += 1
                        logger.info(f"[SCHEDULER] Profile reminder sent → {user.email}")
                    else:
                        logger.warning(f"[SCHEDULER] Profile reminder failed → {user.email}")
                except Exception as e:
                    logger.error(f"[SCHEDULER] Error sending profile reminder to {user.email}: {e}")

            logger.info(f"[SCHEDULER] Profile reminders: {sent}/{len(veterans)} sent")

        except Exception as e:
            logger.exception(f"[SCHEDULER] veteran_profile_reminders job failed: {e}")


# ─────────────────────────────────────────────────────────────
# JOB 2 — JOB TIPS EMAIL
# Sends to veterans who completed profile 2+ days ago.
# Uses a flag on the user/profile to ensure it's sent once only.
# ─────────────────────────────────────────────────────────────
def send_job_tips_emails(app):
    with app.app_context():
        try:
            from models import User, VeteranProfile
            from services.brevo_service import BrevoService
            from app import db

            cutoff = datetime.utcnow() - timedelta(days=2)

            # Find veterans who completed onboarding 2+ days ago
            # and haven't received job tips yet (job_tips_sent=False)
            veterans = (
                User.query
                .join(VeteranProfile, User.id == VeteranProfile.user_id)
                .filter(
                    User.user_type            == "veteran",
                    User.is_verified          == True,
                    User.onboarding_completed == True,
                    VeteranProfile.job_tips_sent == False,
                    VeteranProfile.updated_at    <= cutoff
                )
                .all()
            )

            if not veterans:
                logger.info("[SCHEDULER] No veterans need job tips today")
                return

            brevo = BrevoService()
            sent  = 0

            for user in veterans:
                try:
                    success = brevo.send_job_tips_email(user)
                    if success:
                        # Mark as sent so we never send it twice
                        profile = user.veteran_profile
                        if profile:
                            profile.job_tips_sent = True
                            db.session.commit()
                        sent += 1
                        logger.info(f"[SCHEDULER] Job tips sent → {user.email}")
                    else:
                        logger.warning(f"[SCHEDULER] Job tips failed → {user.email}")
                except Exception as e:
                    logger.error(f"[SCHEDULER] Error sending job tips to {user.email}: {e}")

            logger.info(f"[SCHEDULER] Job tips: {sent}/{len(veterans)} sent")

        except Exception as e:
            logger.exception(f"[SCHEDULER] send_job_tips_emails job failed: {e}")


# ─────────────────────────────────────────────────────────────
# JOB 3 — EMPLOYER POST JOB REMINDER
# Sends to employers who completed profile 3+ days ago
# but haven't posted any jobs yet.
# ─────────────────────────────────────────────────────────────
def send_employer_post_job_reminders(app):
    with app.app_context():
        try:
            from models import User, EmployerProfile, JobPosting
            from services.brevo_service import BrevoService

            cutoff = datetime.utcnow() - timedelta(days=3)

            employers = (
                User.query
                .join(EmployerProfile, User.id == EmployerProfile.user_id)
                .filter(
                    User.user_type                == "employer",
                    User.is_verified              == True,
                    EmployerProfile.profile_completed == True,
                    EmployerProfile.updated_at        <= cutoff
                )
                .all()
            )

            if not employers:
                logger.info("[SCHEDULER] No employers need post-job reminder today")
                return

            brevo = BrevoService()
            sent  = 0

            for user in employers:
                # Only remind if they have zero job postings
                job_count = JobPosting.query.filter_by(posted_by=user.id).count()
                if job_count > 0:
                    continue

                try:
                    success = brevo.send_transactional_email(
                        to_email=user.email,
                        to_name=user.first_name or user.username,
                        template_key="employer_post_job_reminder",
                        params={"FIRSTNAME": user.first_name or user.username}
                    )
                    if success:
                        sent += 1
                        logger.info(f"[SCHEDULER] Post-job reminder sent → {user.email}")
                    else:
                        logger.warning(f"[SCHEDULER] Post-job reminder failed → {user.email}")
                except Exception as e:
                    logger.error(f"[SCHEDULER] Error sending post-job reminder to {user.email}: {e}")

            logger.info(f"[SCHEDULER] Post-job reminders: {sent} sent")

        except Exception as e:
            logger.exception(f"[SCHEDULER] send_employer_post_job_reminders job failed: {e}")


# ─────────────────────────────────────────────────────────────
# JOB 4 — EMPLOYER HIRING TIPS
# Sends to employers who have posted at least 1 job
# but haven't received hiring tips yet.
# ─────────────────────────────────────────────────────────────
def send_employer_hiring_tips(app):
    with app.app_context():
        try:
            from models import User, EmployerProfile, JobPosting
            from services.brevo_service import BrevoService
            from app import db

            employers = (
                User.query
                .join(EmployerProfile, User.id == EmployerProfile.user_id)
                .filter(
                    User.user_type                    == "employer",
                    User.is_verified                  == True,
                    EmployerProfile.profile_completed == True,
                    EmployerProfile.hiring_tips_sent  == False,
                )
                .all()
            )

            if not employers:
                logger.info("[SCHEDULER] No employers need hiring tips today")
                return

            brevo = BrevoService()
            sent  = 0

            for user in employers:
                # Only send if they have at least 1 job posting
                job_count = JobPosting.query.filter_by(posted_by=user.id).count()
                if job_count == 0:
                    continue

                try:
                    success = brevo.send_transactional_email(
                        to_email=user.email,
                        to_name=user.first_name or user.username,
                        template_key="employer_hiring_tips",
                        params={"FIRSTNAME": user.first_name or user.username}
                    )
                    if success:
                        # Mark as sent — one time only
                        profile = user.employer_profile
                        if profile:
                            profile.hiring_tips_sent = True
                            db.session.commit()
                        sent += 1
                        logger.info(f"[SCHEDULER] Hiring tips sent → {user.email}")
                    else:
                        logger.warning(f"[SCHEDULER] Hiring tips failed → {user.email}")
                except Exception as e:
                    logger.error(f"[SCHEDULER] Error sending hiring tips to {user.email}: {e}")

            logger.info(f"[SCHEDULER] Hiring tips: {sent} sent")

        except Exception as e:
            logger.exception(f"[SCHEDULER] send_employer_hiring_tips job failed: {e}")




# ─────────────────────────────────────────────────────────────
# JOB 5 — DAILY APPLICATION SUMMARY EMAIL TO ADMIN
# Runs at 8:00 PM Lagos time every day
# Sends: total applications today, which jobs, any failures
# ─────────────────────────────────────────────────────────────
def send_daily_application_summary(app):
    with app.app_context():
        try:
            from models import JobApplication, JobPosting, User
            from app import db
            from sqlalchemy import func
            import requests as _requests
            import os

            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            # Get today's applications
            applications = db.session.query(
                JobApplication, JobPosting, User
            ).join(
                JobPosting, JobApplication.job_id == JobPosting.id
            ).join(
                User, JobApplication.veteran_id == User.id
            ).filter(
                JobApplication.created_at >= today_start
            ).all()

            total = len(applications)

            if total == 0:
                logger.info("[SCHEDULER] No applications today — skipping summary email")
                return

            # Build job breakdown
            job_breakdown = {}
            for app_record, job, veteran in applications:
                key = f"{job.title} at {job.company_name}"
                if key not in job_breakdown:
                    job_breakdown[key] = []
                job_breakdown[key].append(veteran.full_name or veteran.email)

            rows = ""
            for job_title, applicants in job_breakdown.items():
                rows += f"""
                <tr>
                  <td style="padding:10px;border-bottom:1px solid #eee;font-size:14px;">{job_title}</td>
                  <td style="padding:10px;border-bottom:1px solid #eee;font-size:14px;text-align:center;">{len(applicants)}</td>
                  <td style="padding:10px;border-bottom:1px solid #eee;font-size:13px;color:#666;">{', '.join(applicants)}</td>
                </tr>"""

            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;">
              <div style="background:#0d2137;padding:24px;text-align:center;">
                <h2 style="color:#d4af37;margin:0;">Daily Application Summary</h2>
                <p style="color:rgba(255,255,255,0.6);margin:8px 0 0;font-size:14px;">
                  {datetime.utcnow().strftime('%A, %d %B %Y')}
                </p>
              </div>
              <div style="padding:24px;background:#f9f9f9;">
                <div style="background:#fff;border-left:4px solid #d4af37;padding:16px;margin-bottom:24px;border-radius:4px;">
                  <p style="margin:0;font-size:28px;font-weight:700;color:#0d2137;">{total}</p>
                  <p style="margin:4px 0 0;font-size:14px;color:#666;">Total applications submitted today</p>
                </div>
                <h3 style="color:#0d2137;font-size:16px;margin:0 0 12px;">Breakdown by Job</h3>
                <table width="100%" style="border-collapse:collapse;background:#fff;border:1px solid #eee;border-radius:4px;">
                  <thead>
                    <tr style="background:#0d2137;">
                      <th style="padding:10px;color:#d4af37;font-size:12px;text-align:left;">Job</th>
                      <th style="padding:10px;color:#d4af37;font-size:12px;text-align:center;">Count</th>
                      <th style="padding:10px;color:#d4af37;font-size:12px;text-align:left;">Applicants</th>
                    </tr>
                  </thead>
                  <tbody>{rows}</tbody>
                </table>
                <p style="font-size:12px;color:#999;margin-top:24px;">
                  VetJobPortal Admin System — automated daily report
                </p>
              </div>
            </div>"""

            api_key = os.environ.get('BREVO_API_KEY')
            if not api_key:
                logger.error("[SCHEDULER] No Brevo API key — cannot send daily summary")
                return

            response = _requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "api-key": api_key,
                },
                json={
                    "sender": {"name": "VetJobPortal System", "email": "support@vetjobportal.com"},
                    "to": [{"email": "support@vetjobportal.com", "name": "Admin"}],
                    "subject": f"[VetJobPortal] Daily Summary — {total} Application{'s' if total != 1 else ''} Today",
                    "htmlContent": html,
                },
                timeout=10,
            )

            if response.status_code in (200, 201):
                logger.info(f"[SCHEDULER] Daily summary sent — {total} applications today")
            else:
                logger.error(f"[SCHEDULER] Daily summary failed: {response.status_code} {response.text[:200]}")

        except Exception as e:
            logger.exception(f"[SCHEDULER] send_daily_application_summary failed: {e}")


# ─────────────────────────────────────────────────────────────
# EXCEPTION ALERT — Suspicious activity or submission failure
# Called directly from smart_apply.py (not a scheduled job)
# ─────────────────────────────────────────────────────────────
def send_admin_exception_alert(app, alert_type, details):
    """
    Send immediate alert email to admin for exceptions.

    alert_types:
      - 'suspicious_activity'  : veteran applying to 10+ jobs in 1 hour
      - 'submission_failure'   : email to employer failed to send
    """
    with app.app_context():
        try:
            import requests as _requests
            import os

            if alert_type == 'suspicious_activity':
                subject = "[ALERT] Suspicious Application Activity Detected"
                color = "#ef4444"
                icon = "⚠️"
                body = f"""
                <p style="font-size:15px;color:#333;">A veteran has submitted an unusually high number of applications.</p>
                <div style="background:#fff3f3;border-left:4px solid #ef4444;padding:16px;margin:16px 0;border-radius:4px;">
                  {details}
                </div>
                <p style="font-size:13px;color:#666;">
                  Please review this account in the
                  <a href="https://vetjobportal.com/admin/veterans" style="color:#0d2137;">Veterans Management</a>
                  section.
                </p>"""

            elif alert_type == 'submission_failure':
                subject = "[ALERT] Application Submission Failure"
                color = "#f97316"
                icon = "❌"
                body = f"""
                <p style="font-size:15px;color:#333;">An application submission via email failed.</p>
                <div style="background:#fff8f3;border-left:4px solid #f97316;padding:16px;margin:16px 0;border-radius:4px;">
                  {details}
                </div>
                <p style="font-size:13px;color:#666;">
                  The veteran may need to be contacted manually to complete their application.
                </p>"""
            else:
                subject = f"[ALERT] VetJobPortal System Alert: {alert_type}"
                color = "#6366f1"
                icon = "ℹ️"
                body = f"<p>{details}</p>"

            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
              <div style="background:#0d2137;padding:20px;text-align:center;">
                <h2 style="color:{color};margin:0;">{icon} {subject.replace('[ALERT] ','')}</h2>
                <p style="color:rgba(255,255,255,0.5);font-size:12px;margin:6px 0 0;">
                  {datetime.utcnow().strftime('%d %b %Y at %H:%M UTC')}
                </p>
              </div>
              <div style="padding:24px;background:#f9f9f9;">
                {body}
              </div>
            </div>"""

            api_key = os.environ.get('BREVO_API_KEY')
            if not api_key:
                logger.error("[ALERT] No Brevo API key — cannot send admin alert")
                return

            response = _requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "api-key": api_key,
                },
                json={
                    "sender": {"name": "VetJobPortal Alerts", "email": "support@vetjobportal.com"},
                    "to": [{"email": "support@vetjobportal.com", "name": "Admin"}],
                    "subject": subject,
                    "htmlContent": html,
                },
                timeout=10,
            )

            if response.status_code in (200, 201):
                logger.info(f"[ALERT] Admin alert sent: {alert_type}")
            else:
                logger.error(f"[ALERT] Admin alert failed: {response.status_code}")

        except Exception as e:
            logger.exception(f"[ALERT] send_admin_exception_alert failed: {e}")

# ─────────────────────────────────────────────────────────────
# SCHEDULER INIT
# Call this from create_app() in app.py
# ─────────────────────────────────────────────────────────────
def start_scheduler(app):
    """
    Initialise and start the background scheduler.
    All jobs run daily at staggered times to avoid DB load spikes.
    """
    scheduler = BackgroundScheduler(timezone="Africa/Lagos")

    # Run at 9:00 AM Lagos time daily
    scheduler.add_job(
        func=send_veteran_profile_reminders,
        trigger=CronTrigger(hour=9, minute=0),
        args=[app],
        id="veteran_profile_reminder",
        name="Veteran Profile Reminder",
        replace_existing=True
    )

    # Run at 9:30 AM Lagos time daily
    scheduler.add_job(
        func=send_job_tips_emails,
        trigger=CronTrigger(hour=9, minute=30),
        args=[app],
        id="job_tips",
        name="Job Tips Email",
        replace_existing=True
    )

    # Run at 10:00 AM Lagos time daily
    scheduler.add_job(
        func=send_employer_post_job_reminders,
        trigger=CronTrigger(hour=10, minute=0),
        args=[app],
        id="employer_post_job_reminder",
        name="Employer Post Job Reminder",
        replace_existing=True
    )

    # Run at 10:30 AM Lagos time daily
    scheduler.add_job(
        func=send_employer_hiring_tips,
        trigger=CronTrigger(hour=10, minute=30),
        args=[app],
        id="employer_hiring_tips",
        name="Employer Hiring Tips",
        replace_existing=True
    )

    scheduler.add_job(
         func=lambda: run_full_scrape(flask_app=app),
         trigger='cron',
         hour=7,
         minute=0,
         id='veteran_job_scraper',
         name='Veteran Job Scraper',
         replace_existing=True,
         misfire_grace_time=3600,
    )

    # Run at 8:00 PM Lagos time daily
    scheduler.add_job(
        func=send_daily_application_summary,
        trigger=CronTrigger(hour=20, minute=0),
        args=[app],
        id="daily_application_summary",
        name="Daily Application Summary",
        replace_existing=True
    )

    scheduler.start()
    app.logger.info("[SCHEDULER] Background scheduler started — 4 jobs registered")

    return scheduler