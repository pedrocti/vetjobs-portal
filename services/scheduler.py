# services/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging

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

    scheduler.start()
    app.logger.info("[SCHEDULER] Background scheduler started — 4 jobs registered")

    return scheduler