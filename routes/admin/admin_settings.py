# routes/admin/admin_settings.py

from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from datetime import datetime

from . import admin_bp
from app import db
from models import PlatformSettings


@admin_bp.route('/platform-settings', methods=['GET', 'POST'])
@login_required
def manage_settings():
    """Platform-wide settings management (Admin only)."""

    # 🔐 Admin check (consistent with rest of your app)
    if not current_user.is_admin():
        flash('Access denied. Administrators only.', 'error')
        return redirect(url_for('admin.dashboard'))

    try:
        # =============================
        # 📦 Load or Create Settings
        # =============================
        settings = PlatformSettings.query.first()

        if not settings:
            settings = PlatformSettings(
                platform_name="VetWorkConnect",
                veteran_label="Veteran",
                employer_label="Employer",
                updated_at=datetime.utcnow()
            )
            db.session.add(settings)
            db.session.commit()

        # =============================
        # 📝 Handle Form Submission
        # =============================
        if request.method == 'POST':
            settings.platform_name = request.form.get(
                'platform_name', settings.platform_name
            )
            settings.veteran_label = request.form.get(
                'veteran_label', settings.veteran_label
            )
            settings.employer_label = request.form.get(
                'employer_label', settings.employer_label
            )
            settings.updated_at = datetime.utcnow()

            db.session.commit()

            flash('Platform settings updated successfully!', 'success')
            return redirect(url_for('admin.manage_settings'))

        # =============================
        # 📄 Render Page
        # =============================
        return render_template(
            'admin/settings.html',
            settings=settings
        )

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in platform settings: {e}")
        flash('Something went wrong while loading settings.', 'error')
        return redirect(url_for('admin.dashboard'))