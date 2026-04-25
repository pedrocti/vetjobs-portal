import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """
    Base configuration — all shared settings live here.
    Environment-specific classes override only what differs.
    All Brevo config is inside the class so Flask app.config picks it up.
    """

    # ───────────────────────────────────────────
    # CORE APP
    # ───────────────────────────────────────────
    SECRET_KEY = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(basedir, 'veteran_portal.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 300,
        "pool_pre_ping": True,
    }

    # ───────────────────────────────────────────
    # BASE URL
    # On Replit: set BASE_URL secret to your full
    # Replit app URL e.g. https://yourapp.repl.co
    # On production: set to https://vetjobportal.com
    # Never leave as localhost in any live environment.
    # ───────────────────────────────────────────
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")

    # ───────────────────────────────────────────
    # BREVO — all keys inside the class
    # Set these as Replit Secrets (dev) or
    # environment variables (production).
    # ───────────────────────────────────────────
    BREVO_API_KEY = os.environ.get("BREVO_API_KEY")

    # Must match your verified sender in Brevo → Senders & IPs
    BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "support@vetjobportal.com")
    BREVO_SENDER_NAME  = os.environ.get("BREVO_SENDER_NAME",  "VetJobPortal")

    # Brevo Contact List IDs — get from Brevo → Contacts → Lists
    # Click a list → the ID is in the URL: /contacts/lists/ID
    BREVO_LIST_VETERANS  = int(os.environ.get("BREVO_LIST_VETERANS",  0))
    BREVO_LIST_EMPLOYERS = int(os.environ.get("BREVO_LIST_EMPLOYERS", 0))

    # ───────────────────────────────────────────
    # FILE UPLOADS
    # ───────────────────────────────────────────
    UPLOAD_FOLDER    = os.path.join(basedir, "static", "uploads")
    RESUME_FOLDER    = os.path.join(UPLOAD_FOLDER, "resumes")
    ID_FOLDER        = os.path.join(UPLOAD_FOLDER, "id")
    DISCHARGE_FOLDER = os.path.join(UPLOAD_FOLDER, "discharge")

    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "pdf"}
    RESUME_EXTENSIONS  = {"pdf", "doc", "docx"}

    # ───────────────────────────────────────────
    # PLATFORM
    # ───────────────────────────────────────────
    PLATFORM_LOGO = "images/vetjoblogo1.png"

    # ───────────────────────────────────────────
    # ENSURE UPLOAD FOLDERS EXIST ON STARTUP
    # ───────────────────────────────────────────
    @staticmethod
    def init_app(app):
        os.makedirs(Config.RESUME_FOLDER,    exist_ok=True)
        os.makedirs(Config.ID_FOLDER,        exist_ok=True)
        os.makedirs(Config.DISCHARGE_FOLDER, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# DEVELOPMENT CONFIG
# Used on Replit and local machines.
# BASE_URL must be set as a Replit Secret to your Replit URL.
# ═══════════════════════════════════════════════════════════════
class DevelopmentConfig(Config):
    DEBUG = True

    # Replit Secret: BASE_URL = https://yourapp.repl.co
    # If not set, verify links will use localhost and break.
    BASE_URL = os.environ.get("BASE_URL", "http://localhost:5000")


# ═══════════════════════════════════════════════════════════════
# PRODUCTION CONFIG
# All values must come from environment — no hardcoded fallbacks.
# ═══════════════════════════════════════════════════════════════
class ProductionConfig(Config):
    DEBUG = False

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")

    # Production must have BASE_URL set — no fallback intentionally
    BASE_URL = os.environ.get("BASE_URL")

    # Tighten session cookie security in production
    SESSION_COOKIE_SECURE   = True
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = "Lax"


# ═══════════════════════════════════════════════════════════════
# TESTING CONFIG
# ═══════════════════════════════════════════════════════════════
class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    BASE_URL = "http://localhost:5000"
    WTF_CSRF_ENABLED = False


# ═══════════════════════════════════════════════════════════════
# CONFIG SELECTOR
# In your app factory: app.config.from_object(config[env])
# Set FLASK_ENV=development or production in your secrets.
# ═══════════════════════════════════════════════════════════════
config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
    "default":     DevelopmentConfig,
}