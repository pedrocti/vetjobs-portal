import os
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template_string


class EmailService:
    """
    VetJobPortal Email Service.
    Reads SMTP config from the EmailSetting database table
    (managed via Admin Dashboard). Falls back to SendGrid if configured.
    """

    def __init__(self):
        try:
            from models import EmailSetting
            self.EmailSetting = EmailSetting
        except Exception:
            self.EmailSetting = None

        self._load_settings()

    def _full_url(self, path):
        base_url = current_app.config.get("BASE_URL", "")
        return f"{base_url}{path}"

    def _brevo_managed(self, email_type: str) -> bool:
        """
        Prevent sending emails that are handled by Brevo automation.
        Controlled via config.
        """
        managed = current_app.config.get("BREVO_MANAGED_EMAILS", [])
        return email_type in managed

    # ─────────────────────────────────────────────────────────
    # SETTINGS LOADER
    # ─────────────────────────────────────────────────────────

    def _load_settings(self):
        """Load SMTP settings from database. Falls back to env vars."""
        self.smtp_enabled  = False
        self.smtp_host     = ''
        self.smtp_port     = 465
        self.smtp_use_tls  = False
        self.smtp_username = ''
        self.smtp_password = ''
        self.from_email    = 'support@vetjobportal.com'
        self.from_name     = 'VetJobPortal'

        if self.EmailSetting:
            try:
                self.smtp_enabled  = self.EmailSetting.get_setting('smtp_enabled',  False)
                self.smtp_host     = self.EmailSetting.get_setting('smtp_host',     '')
                self.smtp_port     = self.EmailSetting.get_setting('smtp_port',     465)
                self.smtp_use_tls  = self.EmailSetting.get_setting('smtp_use_tls',  False)
                self.smtp_username = self.EmailSetting.get_setting('smtp_username', '')
                self.smtp_password = self.EmailSetting.get_setting('smtp_password', '')
                self.from_email    = self.EmailSetting.get_setting('from_email',    'support@vetjobportal.com')
                self.from_name     = self.EmailSetting.get_setting('from_name',     'VetJobPortal')
            except Exception as e:
                if current_app:
                    current_app.logger.warning(f"Could not load email settings from DB: {e}")

        # SendGrid fallback
        self.sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')

    # ─────────────────────────────────────────────────────────
    # CORE SEND METHOD
    # ─────────────────────────────────────────────────────────

    def send_email(self, to_email, subject, html_content=None, text_content=None):
        """
        Send email using SMTP (from admin dashboard config).
        Falls back to Brevo API if SMTP not configured.
        Falls back to SendGrid if Brevo not configured.
        Logs email if no delivery method available.
        """
        # Reload settings fresh each call so admin changes apply immediately
        self._load_settings()

        if self.smtp_enabled and self.smtp_host and self.smtp_username and self.smtp_password:
            return self._send_smtp(to_email, subject, html_content, text_content)

        # Brevo API fallback (primary fallback — already configured on this platform)
        brevo_key = os.environ.get('BREVO_API_KEY')
        if brevo_key:
            return self._send_brevo(to_email, subject, html_content, text_content, brevo_key)

        if self.sendgrid_api_key:
            return self._send_sendgrid(to_email, subject, html_content, text_content)

        # Log only — no delivery method configured
        if current_app:
            current_app.logger.warning(
                f"[EMAIL NOT SENT] No delivery method configured.\n"
                f"To: {to_email} | Subject: {subject}"
            )
        return False

    def _send_brevo(self, to_email, subject, html_content=None, text_content=None, api_key=None):
        """Send via Brevo transactional API — used as SMTP fallback."""
        import requests as _requests
        try:
            payload = {
                "sender": {
                    "name": self.from_name or "VetJobPortal",
                    "email": self.from_email or "support@vetjobportal.com"
                },
                "to": [{"email": to_email}],
                "subject": subject,
            }
            if html_content:
                payload["htmlContent"] = html_content
            if text_content:
                payload["textContent"] = text_content

            response = _requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={
                    "accept": "application/json",
                    "content-type": "application/json",
                    "api-key": api_key,
                },
                json=payload,
                timeout=10,
            )
            if response.status_code in (200, 201, 202):
                if current_app:
                    current_app.logger.info(f"[BREVO SENT] To: {to_email} | Subject: {subject}")
                return True
            else:
                if current_app:
                    current_app.logger.error(
                        f"[BREVO ERROR] {response.status_code} | {response.text[:200]}"
                    )
                return False
        except Exception as e:
            if current_app:
                current_app.logger.error(f"[BREVO EXCEPTION] {e}")
            return False

    # ─────────────────────────────────────────────────────────
    # SMTP SENDER
    # ─────────────────────────────────────────────────────────

    def _send_smtp(self, to_email, subject, html_content=None, text_content=None):
        """Send via SMTP — supports both port 465 (SSL) and 587 (STARTTLS)."""
        try:
            msg = MIMEMultipart('alternative')
            msg['From']    = f"{self.from_name} <{self.from_email}>"
            msg['To']      = to_email
            msg['Subject'] = subject

            if text_content:
                msg.attach(MIMEText(text_content, 'plain'))
            if html_content:
                msg.attach(MIMEText(html_content, 'html'))

            port = int(self.smtp_port)

            if port == 465:
                # SSL — Hostinger default
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.smtp_host, port, context=context) as server:
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:
                # STARTTLS — port 587
                with smtplib.SMTP(self.smtp_host, port) as server:
                    server.ehlo()
                    if self.smtp_use_tls:
                        server.starttls()
                        server.ehlo()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)

            if current_app:
                current_app.logger.info(f"[EMAIL SENT] To: {to_email} | Subject: {subject}")
            return True

        except Exception as e:
            if current_app:
                current_app.logger.error(f"[SMTP ERROR] {e}")
            return False

    # ─────────────────────────────────────────────────────────
    # SENDGRID FALLBACK
    # ─────────────────────────────────────────────────────────

    def _send_sendgrid(self, to_email, subject, html_content=None, text_content=None):
        """Send via SendGrid as fallback."""
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject
            )

            content_list = []
            if text_content:
                content_list.append(Content("text/plain", text_content))
            if html_content:
                content_list.append(Content("text/html", html_content))
            message.content = content_list

            client   = SendGridAPIClient(self.sendgrid_api_key)
            response = client.send(message)

            if response.status_code in [200, 202]:
                if current_app:
                    current_app.logger.info(f"[EMAIL SENT via SendGrid] To: {to_email}")
                return True
            else:
                if current_app:
                    current_app.logger.error(f"[SENDGRID ERROR] Status: {response.status_code}")
                return False

        except Exception as e:
            if current_app:
                current_app.logger.error(f"[SENDGRID ERROR] {e}")
            return False

    # ─────────────────────────────────────────────────────────
    # BRANDED HTML TEMPLATE
    # ─────────────────────────────────────────────────────────

    def _build_html(self, user_name, subject, body, action_url=None, action_text=None):
        """
        Build a branded VetJobPortal HTML email.
        Uses inline CSS for maximum email client compatibility.
        """
        action_block = ''
        if action_url and action_text:
            action_block = f"""
            <div style="text-align:center;margin:32px 0;">
              <a href="{action_url}"
                 style="display:inline-block;padding:14px 32px;
                        background:#D4AF37;color:#0a1628;
                        font-family:Arial,sans-serif;font-size:14px;
                        font-weight:700;letter-spacing:1px;
                        text-decoration:none;border-radius:2px;">
                {action_text}
              </a>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background:#04080f;font-family:Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#04080f;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0"
               style="max-width:600px;width:100%;
                      background:#0a1628;
                      border:1px solid rgba(212,175,55,0.2);
                      border-radius:12px;
                      overflow:hidden;">

          <!-- GOLD TOP BAR -->
          <tr>
            <td style="height:3px;
                       background:linear-gradient(90deg,transparent,#D4AF37,#f0d060,#D4AF37,transparent);">
            </td>
          </tr>

          <!-- HEADER -->
          <tr>
            <td style="background:#080f20;padding:36px 40px;text-align:center;
                       border-bottom:1px solid rgba(212,175,55,0.12);">
              <p style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;
                        letter-spacing:4px;text-transform:uppercase;
                        color:#D4AF37;margin:0 0 8px;">
                VETJOBPORTAL
              </p>
              <p style="font-family:Georgia,serif;font-size:22px;font-weight:700;
                        color:#ffffff;margin:0;line-height:1.3;">
                {subject}
              </p>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="padding:40px;">

              <p style="font-size:15px;color:rgba(255,255,255,0.8);
                        line-height:1.6;margin:0 0 16px;">
                Dear <strong style="color:#ffffff;">{user_name}</strong>,
              </p>

              <div style="font-size:15px;color:rgba(255,255,255,0.65);
                          line-height:1.8;white-space:pre-line;">
                {body}
              </div>

              {action_block}

              <p style="font-size:13px;color:rgba(255,255,255,0.35);
                        line-height:1.7;margin:32px 0 0;
                        border-top:1px solid rgba(255,255,255,0.06);
                        padding-top:24px;">
                If you did not request this email, you can safely ignore it.
                For support, contact us at
                <a href="mailto:support@vetjobportal.com"
                   style="color:#D4AF37;text-decoration:none;">
                  support@vetjobportal.com
                </a>
              </p>

            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#04080f;padding:24px 40px;text-align:center;
                       border-top:1px solid rgba(212,175,55,0.08);">
              <p style="font-size:11px;color:rgba(255,255,255,0.25);margin:0 0 6px;
                        font-family:Arial,sans-serif;letter-spacing:1px;">
                &copy; {datetime.now().year} VetJobPortal &nbsp;|&nbsp;
                Connecting Nigerian Veterans With Opportunity
              </p>
              <p style="font-size:11px;color:rgba(255,255,255,0.2);margin:0;
                        font-family:Arial,sans-serif;">
                This is an automated message. Please do not reply to this email.
              </p>
            </td>
          </tr>

          <!-- GOLD BOTTOM BAR -->
          <tr>
            <td style="height:2px;background:linear-gradient(90deg,transparent,#D4AF37,transparent);">
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""

    def _build_text(self, body, action_url=None, action_text=None):
        """Plain text fallback."""
        lines = [
            "VetJobPortal — Connecting Nigerian Veterans With Opportunity",
            "=" * 60,
            "",
            body,
            "",
        ]
        if action_url and action_text:
            lines += [f"{action_text}: {action_url}", ""]
        lines += [
            "-" * 60,
            f"© {datetime.now().year} VetJobPortal",
            "support@vetjobportal.com",
            "This is an automated message. Please do not reply.",
        ]
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    # NOTIFICATION EMAIL (generic)
    # ─────────────────────────────────────────────────────────

    def send_notification_email(self, user, subject, body,
                                action_url=None, action_text=None, category='general'):
        html = self._build_html(user.first_name, subject, body, action_url, action_text)
        text = self._build_text(body, action_url, action_text)
        return self.send_email(user.email, subject, html, text)


    # ─────────────────────────────────────────────────────────
    # EMPLOYER VERIFICATION STATUS EMAIL
    # ─────────────────────────────────────────────────────────
    def send_employer_verification_status_email(self, user, status, admin_note=None):
        """Send approval or rejection email to employer."""
        if status == 'approved':
            subject = "Employer Account Approved — VetJobPortal"
            body = (
                f"Congratulations {user.first_name},\n\n"
                "Your employer account on VetJobPortal has been reviewed and approved.\n\n"
                "You can now post jobs, search our verified veteran talent pool, "
                "and begin building your military-trained workforce.\n\n"
                "If you have not already done so, complete your company profile "
                "to increase visibility with veterans."
            )
            action_url  = self._full_url("/dashboard/employer")
            action_text = "Go to Dashboard"
        else:
            subject = "Employer Account — Verification Update"
            body = (
                f"Dear {user.first_name},\n\n"
                "Your VetJobPortal employer account could not be approved at this time.\n\n"
                f"Reason: {admin_note or 'Please contact support for more information.'}\n\n"
                "If you believe this is an error or have additional documents to submit, "
                "please contact our support team."
            )
            action_url  = self._full_url("/contact")
            action_text = "Contact Support"

        return self.send_notification_email(
            user=user,
            subject=subject,
            body=body,
            action_url=action_url,
            action_text=action_text
        )

    # ─────────────────────────────────────────────────────────
    # ADMIN ALERT EMAIL (generic — for actions requiring review)
    # ─────────────────────────────────────────────────────────
    def send_admin_action_alert(self, admin_email, subject, body, action_url=None, action_text=None):
        """Send an alert email directly to admin email address."""
        html = self._build_html("Admin", subject, body, action_url, action_text)
        text = self._build_text(body, action_url, action_text)
        return self.send_email(admin_email, subject, html, text)


    # ─────────────────────────────────────────────────────────
    # MARKETPLACE REQUEST CONFIRMATION (to client)
    # ─────────────────────────────────────────────────────────
    def send_marketplace_request_confirmation(self, client_email, client_name,
                                               role_needed, reference_id):
        """Confirm to client that their request was received."""
        subject = f"Request Received — {role_needed} | VetJobPortal"
        body = (
            f"Dear {client_name},\n\n"
            f"Your request for a verified {role_needed} has been received successfully.\n\n"
            f"Reference: VJP-{reference_id}\n\n"
            "Our team will review your request and match you with a suitable veteran "
            "within 24 hours. You will receive a follow-up email once a match is confirmed.\n\n"
            "What happens next:\n"
            "1. Our team reviews your requirements\n"
            "2. We select the best-fit verified veteran\n"
            "3. We introduce you via email within 24 hours\n\n"
            "If you have urgent requirements, reply to this email or contact us directly."
        )
        html = self._build_html(client_name, subject, body,
                                action_url=self._full_url("/marketplace"),
                                action_text="View Verified Workforce")
        text = self._build_text(body)
        return self.send_email(client_email, subject, html, text)

    # ─────────────────────────────────────────────────────────
    # MARKETPLACE CLIENT MATCH EMAIL (to client when paired)
    # ─────────────────────────────────────────────────────────
    def send_marketplace_client_match_email(self, client_email, client_name,
                                             role_needed, veteran_name, admin_notes=None):
        """Notify client they have been matched with a veteran."""
        subject = f"Match Confirmed — {role_needed} | VetJobPortal"
        body = (
            f"Dear {client_name},\n\n"
            f"Great news — we have matched a verified veteran to your {role_needed} request.\n\n"
            f"Matched Professional: {veteran_name}\n"
            f"{('Notes from our team: ' + admin_notes) if admin_notes else ''}\n\n"
            "Our team will be in touch shortly to facilitate the introduction and "
            "confirm the engagement details.\n\n"
            "All our veterans are background-checked, identity-verified and service-record "
            "confirmed before placement."
        )
        html = self._build_html(client_name, subject, body,
                                action_url=self._full_url("/contact"),
                                action_text="Contact Our Team")
        text = self._build_text(body)
        return self.send_email(client_email, subject, html, text)

    # ─────────────────────────────────────────────────────────
    # MARKETPLACE MATCH EMAIL
    # ─────────────────────────────────────────────────────────
    def send_marketplace_match_email(self, veteran, role_needed, client_name, admin_notes=None):
        """Notify veteran they have been matched to a service request."""
        subject = f"Assignment Match — {role_needed}"
        body = (
            f"Dear {veteran.first_name},\n\n"
            f"You have been matched to a service request for a {role_needed} role "
            f"from {client_name}.\n\n"
            f"{('Additional notes: ' + admin_notes) if admin_notes else ''}\n\n"
            "Please log in to your dashboard to view the full details and confirm your availability."
        )
        return self.send_notification_email(
            user=veteran,
            subject=subject,
            body=body,
            action_url=self._full_url("/dashboard"),
            action_text="View Assignment"
        )

    # ─────────────────────────────────────────────────────────
    # EMAIL VERIFICATION (NEW)
    # ─────────────────────────────────────────────────────────
    def send_verification_email(self, user, verify_link):
        """
        Send email verification link.
        Skips if handled by Brevo automation.
        """

        if self._brevo_managed("verification"):
            if current_app:
                current_app.logger.info("[EMAIL SKIPPED] Verification handled by Brevo")
            return True

        subject = "Verify Your Email — VetJobPortal"

        body = (
            "Welcome to VetJobPortal.\n\n"
            "Before you can access your account, please verify your email address.\n\n"
            "Click the button below to confirm your email. "
            "This link expires in 1 hour for your security.\n\n"
            "If you did not create this account, you can safely ignore this message."
        )

        return self.send_notification_email(
            user=user,
            subject=subject,
            body=body,
            action_url=verify_link,
            action_text="Verify My Email"
        )
        
    # ─────────────────────────────────────────────────────────
    # WELCOME EMAIL
    # ─────────────────────────────────────────────────────────

    def send_welcome_email(self, user):
        # Prevent duplicate welcome emails if Brevo handles it
        if self._brevo_managed("welcome"):
            if current_app:
                current_app.logger.info("[EMAIL SKIPPED] Welcome handled by Brevo")
            return True

        subject = f"Welcome to VetJobPortal, {user.first_name}!"

        if user.is_veteran():
            body = (
                "Thank you for joining VetJobPortal — Nigeria's first dedicated "
                "military veteran transition and employment pathway.\n\n"
                "Your next mission starts here. Complete your profile to unlock "
                "job matches, CV optimization, and access to employers who "
                "genuinely value military experience.\n\n"
                "Honor. Discipline. Service. — That's the talent we represent."
            )
            action_url = self._full_url("/veteran/complete-profile")
            action_text = "Complete Your Profile"

        elif user.is_employer():
            body = (
                "Thank you for joining VetJobPortal as an employer partner.\n\n"
                "You now have access to a curated pool of disciplined, "
                "mission-ready professionals — Nigerian military veterans "
                "trained to lead, execute, and deliver.\n\n"
                "Post your first job and start connecting with proven talent today."
            )
            action_url = self._full_url("/employer/post-job")
            action_text = "Post Your First Job"

        else:
            body = "Your VetJobPortal account has been created successfully."
            action_url  = self._full_url("/dashboard")
            action_text = "Go to Dashboard"

        return self.send_notification_email(
            user=user,
            subject=subject,
            body=body,
            action_url=action_url,
            action_text=action_text
        )

    # ─────────────────────────────────────────────────────────
    # PASSWORD RESET EMAIL
    # ─────────────────────────────────────────────────────────

    def send_password_reset_email(self, user, reset_link):
        subject = "Password Reset Request — VetJobPortal"

        body = (
            "We received a request to reset your VetJobPortal password.\n\n"
            "Click the button below to create a new password. "
            "This link expires in 1 hour for your security.\n\n"
            "If you did not request a password reset, no action is needed "
            "and your account remains secure."
        )

        return self.send_notification_email(
            user=user,
            subject=subject,
            body=body,
            action_url=reset_link,  
            action_text="Reset My Password"
        )

    # ─────────────────────────────────────────────────────────
    # DONATION RECEIPT EMAIL (to donor)
    # ─────────────────────────────────────────────────────────

    def send_donation_receipt_email(self, donor_email, amount, reference):
        subject = "Thank You for Supporting Veterans — VetJobPortal"
        body = (
            f"Your donation of ₦{amount:,.2f} has been received.\n\n"
            "Your generosity helps Nigerian military veterans transition "
            "into meaningful civilian careers — funding CV support, "
            "career training, and job placement services.\n\n"
            f"Transaction Reference: {reference}\n\n"
            "Thank you for standing with those who served."
        )
        html = self._build_html("Supporter", subject, body)
        text = self._build_text(body)
        return self.send_email(donor_email, subject, html, text)

    # ─────────────────────────────────────────────────────────
    # DONATION ADMIN ALERT (to admin inbox)
    # ─────────────────────────────────────────────────────────

    def send_donation_admin_alert(self, amount, donor_email, note,
                                  donation_type, privacy, reference):
        subject = f"New Donation Received — ₦{amount:,.2f}"
        body = (
            f"Amount:     ₦{amount:,.2f}\n"
            f"Type:       {donation_type}\n"
            f"Privacy:    {privacy}\n"
            f"Donor:      {donor_email}\n"
            f"Reference:  {reference}\n\n"
            f"Donor Note:\n{note or 'No note provided'}"
        )
        html = self._build_html("Admin", subject, body)
        text = self._build_text(body)
        return self.send_email("support@vetjobportal.com", subject, html, text)

    # ─────────────────────────────────────────────────────────
    # PROFILE VERIFICATION EMAIL
    # ─────────────────────────────────────────────────────────

    def send_verification_status_email(self, user, status, admin_note=None):
        if status == 'approved':
            subject = "Profile Verified — You're Ready to Apply!"
            body = (
                "Great news — your VetJobPortal profile has been verified.\n\n"
                "You can now apply for jobs, appear in employer searches, "
                "and access all platform features.\n\n"
                "Your service record is confirmed. Your next mission awaits."
            )
            action_url  = self._full_url("/jobs")
            action_text = "Browse Jobs Now"
        else:
            subject = "Profile Verification Update — Action Required"
            body = (
                "Your VetJobPortal profile verification requires attention.\n\n"
                f"{admin_note or 'Please review your uploaded documents and resubmit.'}\n\n"
                "Log in to update your profile and resubmit for verification."
            )
            action_url = self._full_url("/veteran/complete-profile")
            action_text = "Update Profile"

        return self.send_notification_email(
            user=user,
            subject=subject,
            body=body,
            action_url=action_url,
            action_text=action_text
        )

    # ─────────────────────────────────────────────────────────
    # JOB APPLICATION EMAIL
    # ─────────────────────────────────────────────────────────


    # CV FEEDBACK EMAIL
    def send_cv_feedback_email(self, user, cv_analysis):
        if not cv_analysis:
            return False
        first_name = user.first_name
        score = cv_analysis.get('score', 0)
        strengths = cv_analysis.get('strength_summary', '')
        issues = cv_analysis.get('issues', [])
        target_roles = cv_analysis.get('target_roles', [])
        subject = '{}, we reviewed your CV — here is what we found'.format(first_name)
        if score >= 70: score_color, score_label = '#4CAF50', 'Good foundation'
        elif score >= 50: score_color, score_label = '#D4AF37', 'Needs improvement'
        else: score_color, score_label = '#E57373', 'Needs significant work'
        issues_rows = ''
        for i in issues:
            issues_rows += '<tr><td style="padding:10px 0;border-bottom:1px solid rgba(212,175,55,0.08)">'
            issues_rows += '<p style="margin:0 0 3px;font-size:14px;font-weight:700;color:#fff">{}</p>'.format(i.get('point',''))
            issues_rows += '<p style="margin:0;font-size:13px;color:rgba(255,255,255,0.55);line-height:1.5">{}</p>'.format(i.get('detail',''))
            issues_rows += '</td></tr>'
        roles_html = ''
        if target_roles:
            badges = ''.join('<span style="display:inline-block;margin:4px 6px 4px 0;padding:4px 12px;background:rgba(212,175,55,0.12);border:1px solid rgba(212,175,55,0.3);border-radius:2px;font-size:12px;color:#D4AF37">{}</span>'.format(r) for r in target_roles)
            roles_html = '<p style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.5);letter-spacing:1px;text-transform:uppercase;margin:28px 0 10px">Roles You Could Target</p><div>{}</div>'.format(badges)
        html = self._build_cv_feedback_html(first_name, score, score_color, score_label, strengths, issues_rows, roles_html)
        text = 'VetJobPortal CV Review\n\nDear {},\n\nScore: {}/100 ({})\n\nStrengths:\n{}\n\nIssues:\n'.format(first_name, score, score_label, strengths)
        text += '\n'.join('* {}: {}'.format(i.get('point',''), i.get('detail','')) for i in issues)
        text += '\n\nTarget Roles: {}\n\n1. Fix it yourself using the feedback above.\n2. CV Optimization Service: https://vetjobportal.com/cv-optimize\n\nThe VetJobPortal Team'.format(', '.join(target_roles))
        return self.send_email(user.email, subject, html, text)

    def _build_cv_feedback_html(self, first_name, score, score_color, score_label, strengths, issues_rows, roles_html):
        from datetime import datetime
        return '''<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#04080f;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#04080f;padding:40px 20px;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0a1628;border:1px solid rgba(212,175,55,0.2);border-radius:12px;overflow:hidden;">
<tr><td style="height:3px;background:linear-gradient(90deg,transparent,#D4AF37,#f0d060,#D4AF37,transparent);"></td></tr>
<tr><td style="background:#080f20;padding:32px 40px;text-align:center;border-bottom:1px solid rgba(212,175,55,0.12);">
  <p style="font-size:10px;font-weight:700;letter-spacing:4px;text-transform:uppercase;color:#D4AF37;margin:0 0 8px;">VETJOBPORTAL</p>
  <p style="font-family:Georgia,serif;font-size:20px;font-weight:700;color:#fff;margin:0;">Your CV Review Is Ready</p>
</td></tr>
<tr><td style="padding:36px 40px;">
  <p style="font-size:15px;color:rgba(255,255,255,0.8);margin:0 0 20px;">Dear <strong style="color:#fff;">''' + first_name + '''</strong>,</p>
  <p style="font-size:15px;color:rgba(255,255,255,0.65);line-height:1.8;margin:0 0 28px;">Your account has been verified. You are now part of Nigeria&#39;s first dedicated military-to-civilian career platform. We reviewed your uploaded CV and here is our honest assessment.</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:8px;margin-bottom:28px;">
    <tr><td style="padding:20px 24px;">
      <p style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:rgba(255,255,255,0.4);margin:0 0 8px;">Civilian Readiness Score</p>
      <p style="font-size:36px;font-weight:700;color:''' + score_color + ''';margin:0 0 4px;line-height:1;">''' + str(score) + '''<span style="font-size:18px;color:rgba(255,255,255,0.3);">/100</span></p>
      <p style="font-size:12px;color:''' + score_color + ''';margin:0;">''' + score_label + '''</p>
    </td></tr>
  </table>
  <p style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#4CAF50;font-weight:700;margin:0 0 10px;">&#10022; What Is Working For You</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(76,175,80,0.06);border-left:3px solid #4CAF50;margin-bottom:28px;">
    <tr><td style="padding:16px 20px;"><p style="font-size:14px;color:rgba(255,255,255,0.75);line-height:1.7;margin:0;">''' + strengths + '''</p></td></tr>
  </table>
  <p style="font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#D4AF37;font-weight:700;margin:0 0 10px;">&#9888; What Needs To Be Fixed</p>
  <table width="100%" cellpadding="0" cellspacing="0" style="background:rgba(212,175,55,0.04);border-left:3px solid #D4AF37;margin-bottom:8px;">
    <tr><td style="padding:4px 20px 8px;"><table width="100%" cellpadding="0" cellspacing="0">''' + issues_rows + '''</table></td></tr>
  </table>
  <p style="font-size:13px;color:rgba(255,255,255,0.45);line-height:1.7;margin:16px 0 28px;">Your experience earns you a strong civilian position. Do not let a poorly formatted document be the reason employers miss that.</p>
  ''' + roles_html + '''
  <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;"><tr><td style="height:1px;background:rgba(255,255,255,0.06);"></td></tr></table>
  <p style="font-family:Georgia,serif;font-size:17px;font-weight:700;color:#fff;margin:0 0 20px;">Here Is What You Can Do Next</p>
  <p style="font-size:14px;color:#fff;font-weight:700;margin:0 0 6px;">1. Fix it yourself</p>
  <p style="font-size:13px;color:rgba(255,255,255,0.55);line-height:1.6;margin:0 0 20px;">Use the feedback above. Rewrite each bullet to answer: what was the result of what I did? Add a job title, correct errors, add LinkedIn URL.</p>
  <p style="font-size:14px;color:#fff;font-weight:700;margin:0 0 6px;">2. Let our team handle it professionally</p>
  <p style="font-size:13px;color:rgba(255,255,255,0.55);line-height:1.6;margin:0 0 28px;">Our <strong style="color:#D4AF37;">CV Optimization Service</strong> rewrites, reformats and positions your CV for the civilian roles you are targeting.</p>
  <div style="text-align:center;margin:0 0 28px;">
    <a href="https://vetjobportal.com/cv-optimize" style="display:inline-block;padding:16px 40px;background:#D4AF37;color:#0a1628;font-size:13px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;text-decoration:none;border-radius:2px;">Get My CV Optimized</a>
    <p style="font-size:11px;color:rgba(255,255,255,0.3);margin:10px 0 0;">Professional rewrite &nbsp;&#183;&nbsp; Civilian-ready format &nbsp;&#183;&nbsp; Fast turnaround</p>
  </div>
  <p style="font-size:14px;color:rgba(255,255,255,0.65);line-height:1.8;margin:0;">We are rooting for you, <strong style="color:#fff;">''' + first_name + '''</strong>.<br><br><strong style="color:#fff;">The VetJobPortal Team</strong><br><a href="https://vetjobportal.com" style="color:#D4AF37;text-decoration:none;">vetjobportal.com</a></p>
</td></tr>
<tr><td style="background:#04080f;padding:24px 40px;text-align:center;border-top:1px solid rgba(212,175,55,0.08);">
  <p style="font-size:11px;color:rgba(255,255,255,0.25);margin:0;">&copy; VetJobPortal &nbsp;|&nbsp; Connecting Nigerian Veterans With Opportunity</p>
</td></tr>
<tr><td style="height:2px;background:linear-gradient(90deg,transparent,#D4AF37,transparent);"></td></tr>
</table></td></tr></table></body></html>'''

    def send_application_confirmation_email(self, user, job_title, company_name):
        subject = f"Application Submitted — {job_title}"
        body = (
            f"Your application for {job_title} at {company_name} "
            "has been submitted successfully.\n\n"
            "The employer has been notified and will review your profile. "
            "You'll receive an update once they respond.\n\n"
            "Track all your applications from your dashboard."
        )
        return self.send_notification_email(
            user=user,
            subject=subject,
            body=body,
            action_url=self._full_url("/applications/my-applications"),
            action_text="View My Applications"
        )