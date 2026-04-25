import os
import requests
from flask import current_app
from urllib.parse import quote


class BrevoService:
    CONTACTS_URL = "https://api.brevo.com/v3/contacts"
    SMTP_URL     = "https://api.brevo.com/v3/smtp/email"

    # ─────────────────────────────────────────────
    # TEMPLATE ID REGISTRY
    # All Brevo template IDs live here — one place
    # to update if you ever recreate a template.
    # ─────────────────────────────────────────────
    TEMPLATES = {
        "email_verification":        11,
        "vet_welcome":                1,
        "vet_profile_reminder":       4,
        "job_tips":                   5,
        "employer_welcome":           6,
        "employer_post_job_reminder": 7,
        "employer_hiring_tips":       8,
        "password_reset":            12,
    }

    def __init__(self, app=None):
        app = app or current_app

        self.api_key = (
            app.config.get("BREVO_API_KEY")
            or os.environ.get("BREVO_API_KEY")
        )

        self.sender_email = (
            app.config.get("BREVO_SENDER_EMAIL")
            or os.environ.get("BREVO_SENDER_EMAIL")
            or "noreply@vetjobportal.com"
        )

        self.sender_name = (
            app.config.get("BREVO_SENDER_NAME")
            or os.environ.get("BREVO_SENDER_NAME")
            or "VetJobPortal"
        )

        self.headers = {
            "accept":       "application/json",
            "api-key":      self.api_key,
            "content-type": "application/json"
        }

    # ─────────────────────────────────────────────
    # INTERNAL SAFE REQUEST
    # ─────────────────────────────────────────────
    def _request(self, method, url, **kwargs):
        if not self.api_key:
            current_app.logger.error("[BREVO] Missing API key — cannot send")
            return None

        try:
            response = requests.request(
                method,
                url,
                headers=self.headers,
                timeout=10,
                **kwargs
            )

            if response.status_code in [200, 201, 202, 204]:
                return response

            current_app.logger.error(
                f"[BREVO FAIL] {response.status_code} | {response.text}"
            )
            return None

        except Exception as e:
            current_app.logger.exception(f"[BREVO EXCEPTION] {e}")
            return None

    # ─────────────────────────────────────────────
    # CORE TRANSACTIONAL SENDER
    # All email sending flows through here.
    # ─────────────────────────────────────────────
    def send_transactional_email(self, to_email, to_name, template_key, params=None):
        """
        Send a Brevo template email.

        Args:
            to_email     (str):  Recipient email address
            to_name      (str):  Recipient display name
            template_key (str):  Key from TEMPLATES dict (e.g. "email_verification")
            params       (dict): Variables injected into template via {{ params.X }}

        Returns:
            bool: True if sent, False if failed
        """
        template_id = self.TEMPLATES.get(template_key)

        if not template_id:
            current_app.logger.error(
                f"[BREVO] Unknown template key: '{template_key}'. "
                f"Available: {list(self.TEMPLATES.keys())}"
            )
            return False

        payload = {
            "sender": {
                "email": self.sender_email,
                "name":  self.sender_name
            },
            "to": [
                {
                    "email": to_email,
                    "name":  to_name or to_email
                }
            ],
            "templateId": template_id,
            "params":     params or {}
        }

        res = self._request("POST", self.SMTP_URL, json=payload)

        if res:
            current_app.logger.info(
                f"[BREVO SENT] template={template_key} (#{template_id}) → {to_email}"
            )
            return True

        current_app.logger.error(
            f"[BREVO FAILED] template={template_key} (#{template_id}) → {to_email}"
        )
        return False

    # ─────────────────────────────────────────────
    # VERIFICATION EMAIL
    # ─────────────────────────────────────────────
    def send_verification_email(self, user, verify_url):
        """
        Sends email verification link via Brevo template #11.
        Called immediately after registration.
        """
        return self.send_transactional_email(
            to_email=user.email,
            to_name=user.first_name or user.username,
            template_key="email_verification",
            params={
                "FIRSTNAME":  user.first_name or user.username,
                "VERIFY_URL": verify_url
            }
        )

    # ─────────────────────────────────────────────
    # WELCOME EMAIL
    # ─────────────────────────────────────────────
    def send_welcome_email(self, user):
        """
        Sends role-appropriate welcome email after verification.
        Veteran  → template #1
        Employer → template #6
        """
        if user.user_type == "veteran":
            template_key = "vet_welcome"
        elif user.user_type == "employer":
            template_key = "employer_welcome"
        else:
            current_app.logger.warning(
                f"[BREVO] No welcome template for user_type={user.user_type}"
            )
            return False

        return self.send_transactional_email(
            to_email=user.email,
            to_name=user.first_name or user.username,
            template_key=template_key,
            params={
                "FIRSTNAME": user.first_name or user.username
            }
        )

    # ─────────────────────────────────────────────
    # PROFILE COMPLETION REMINDER
    # ─────────────────────────────────────────────
    def send_profile_reminder_email(self, user):
        """
        Sends profile completion nudge to veterans.
        Template #4.
        """
        return self.send_transactional_email(
            to_email=user.email,
            to_name=user.first_name or user.username,
            template_key="vet_profile_reminder",
            params={
                "FIRSTNAME": user.first_name or user.username
            }
        )

    # ─────────────────────────────────────────────
    # JOB TIPS EMAIL
    # ─────────────────────────────────────────────
    def send_job_tips_email(self, user):
        """
        Sends job tips email to veteran.
        Template #5.
        """
        return self.send_transactional_email(
            to_email=user.email,
            to_name=user.first_name or user.username,
            template_key="job_tips",
            params={
                "FIRSTNAME": user.first_name or user.username
            }
        )

    # ─────────────────────────────────────────────
    # PASSWORD RESET
    # Uncomment + add template ID once created in Brevo
    # ─────────────────────────────────────────────
    def send_password_reset_email(self, user, reset_url):
        return self.send_transactional_email(
            to_email=user.email,
            to_name=user.first_name or user.username,
            template_key="password_reset",
            params={
                "FIRSTNAME": user.first_name or user.username,
                "RESET_URL": reset_url
             }
         )

    # ─────────────────────────────────────────────
    # ADD CONTACT TO BREVO CRM
    # CRM sync only — does NOT send any email
    # ─────────────────────────────────────────────
    def add_contact(self, user):
        if not user or not user.email:
            current_app.logger.warning("[BREVO] add_contact: Invalid user/email")
            return False

        list_id = None

        if user.user_type == "veteran":
            list_id = current_app.config.get("BREVO_LIST_VETERANS")
        elif user.user_type == "employer":
            list_id = current_app.config.get("BREVO_LIST_EMPLOYERS")

        if not list_id or list_id == 0:
            current_app.logger.warning(
                f"[BREVO] add_contact: Missing list ID for user_type={user.user_type}"
            )
            return False

        payload = {
            "email": user.email,
            "attributes": {
                "FIRSTNAME":         user.first_name or "",
                "LASTNAME":          user.last_name or "",
                "USERTYPE":          user.user_type or "",
                "PROFILE_COMPLETED": False,
                "ONBOARDING_STAGE":  "registered"
            },
            "listIds":       [int(list_id)],
            "updateEnabled": True
        }

        res = self._request("POST", self.CONTACTS_URL, json=payload)

        if res:
            current_app.logger.info(f"[BREVO] Contact synced: {user.email}")
            return True

        return False

    # ─────────────────────────────────────────────
    # UPDATE CONTACT ATTRIBUTES
    # ─────────────────────────────────────────────
    def update_attributes(self, user_or_email, attributes: dict):
        email = (
            user_or_email
            if isinstance(user_or_email, str)
            else getattr(user_or_email, "email", None)
        )

        if not email:
            current_app.logger.warning("[BREVO] update_attributes: Invalid email")
            return False

        encoded_email = quote(email)

        res = self._request(
            "PUT",
            f"{self.CONTACTS_URL}/{encoded_email}",
            json={"attributes": attributes, "updateEnabled": True}
        )

        if res:
            current_app.logger.info(f"[BREVO UPDATED] {email}")
            return True

        return self._create_minimal_contact(email, attributes)

    # ─────────────────────────────────────────────
    # CREATE CONTACT FALLBACK
    # ─────────────────────────────────────────────
    def _create_minimal_contact(self, email, attributes):
        payload = {
            "email":         email,
            "attributes":    attributes,
            "updateEnabled": True
        }

        res = self._request("POST", self.CONTACTS_URL, json=payload)

        if res:
            current_app.logger.info(f"[BREVO CREATED] {email}")
            return True

        return False