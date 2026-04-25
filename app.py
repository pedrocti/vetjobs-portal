import os
import logging
from flask import Flask, render_template
from markupsafe import Markup
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_mail import Mail
from config import config


# ===============================
# Logging setup
# ===============================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()


# ===============================
# App Factory
# ===============================
def create_app():
    app = Flask(__name__)

    # Load config
    env = os.getenv("FLASK_ENV", "development")
    app.config.from_object(config.get(env, config["default"]))

    # Secret key
    app.secret_key = app.config["SECRET_KEY"]

    # Proxy fix (for deployment)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # ===============================
    # ✅ UNIFIED FILE STORAGE (FIXED)
    # ===============================
    app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
    app.config['RESUME_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'resumes')
    app.config['ID_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'id')
    app.config['DISCHARGE_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'discharge')
    app.config['TRAINING_UPLOAD_FOLDER'] = os.path.join(app.config['UPLOAD_FOLDER'], 'training')

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
    app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'pdf'}
    app.config['RESUME_EXTENSIONS'] = {'pdf', 'doc', 'docx'}

    # Create folders automatically
    os.makedirs(app.config['RESUME_FOLDER'], exist_ok=True)
    os.makedirs(app.config['ID_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DISCHARGE_FOLDER'], exist_ok=True)
    os.makedirs(app.config['TRAINING_UPLOAD_FOLDER'], exist_ok=True)

    # ===============================
    # Mail config
    # ===============================
    app.config['MAIL_SUPPRESS_SEND'] = False
    mail.init_app(app)

    # ===============================
    # Init extensions
    # ===============================
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'

    # ===============================
    # Models
    # ===============================
    from models import (
        User, VeteranProfile, JobPosting, JobApplication, Payment,
        Subscription, PaymentSetting, Notification, NotificationPreference,
        BroadcastNotification, SavedVeteran, SavedJob, SearchLog, MatchingScore
    )

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ===============================
    # Template filter
    # ===============================
    @app.template_filter('nl2br')
    def nl2br(value):
        if not value:
            return ''
        return Markup(value.replace('\n', '<br>'))

    @app.template_filter('basename')
    def basename_filter(path):
        if not path:
            return ''
        return os.path.basename(path)

    # ===============================
    # Blueprints
    # ===============================
    from routes.main import main_bp
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.veteran import veteran_bp
    from routes.admin import admin_bp
    from routes.employer import employer_bp
    from routes.jobs import jobs_bp
    from routes.applications import applications_bp
    from routes.payments import payments_bp
    from routes.notifications import notifications_bp
    from routes.search import search_bp
    from routes.messaging import messaging_bp
    from routes.admin_resources import admin_resources_bp
    from routes.resources import resources_bp
    from routes.training_programs import training_bp
    from routes.services import services_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(veteran_bp, url_prefix="/veteran")
    app.register_blueprint(admin_bp)
    app.register_blueprint(employer_bp, url_prefix="/employer")
    app.register_blueprint(jobs_bp, url_prefix="/jobs")
    app.register_blueprint(applications_bp, url_prefix="/applications")
    app.register_blueprint(payments_bp, url_prefix="/payments")
    app.register_blueprint(notifications_bp, url_prefix="/notifications")
    app.register_blueprint(search_bp, url_prefix="/search")
    app.register_blueprint(messaging_bp, url_prefix="/messaging")
    app.register_blueprint(admin_resources_bp)
    app.register_blueprint(resources_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(services_bp)

    # ===============================
    # Error handlers
    # ===============================
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template(
            "errors/500.html",
            error_details=str(error) if app.debug else None
        ), 500

    # ===============================
    # DB init
    # ===============================
    with app.app_context():
        db.create_all()

    # Start background email scheduler
    from services.scheduler import start_scheduler
    start_scheduler(app)

    return app


# ===============================
# Run App
# ===============================
app = create_app()

if __name__ == "__main__":
    app.run(debug=True)