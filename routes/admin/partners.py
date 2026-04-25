from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_from_directory, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy import func, desc, or_, case
from datetime import datetime, timedelta
import os
from decimal import Decimal
from . import admin_bp

# Import shared database and models
from app import db
from models import (
    User, VeteranProfile, EmployerProfile, Partner,
    JobPosting, JobApplication, Payment, Subscription,
    PaymentSetting, EmailSetting, Message, Testimonial
)


# ========================
# PARTNERS MANAGEMENT
# ========================

import os
from flask import (
    render_template, request, redirect, url_for,
    flash, current_app
)
from werkzeug.utils import secure_filename
from flask_login import login_required, current_user
from models import db, Partner

# Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/manage_partners', methods=['GET', 'POST'])
@login_required
def manage_partners():
    """Admin view to manage partners"""
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    partners = Partner.query.order_by(Partner.created_at.desc()).all()

    if request.method == 'POST':
        name = request.form.get('name')
        website = request.form.get('website')
        logo_file = request.files.get('logo')

        if not name or not logo_file:
            flash('Name and logo are required.', 'danger')
            return redirect(url_for('admin.manage_partners'))

        if logo_file and allowed_file(logo_file.filename):
            filename = secure_filename(logo_file.filename)

            # ✅ Always save to absolute path under static/uploads/partners
            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'partners')
            os.makedirs(upload_folder, exist_ok=True)

            logo_path = os.path.join(upload_folder, filename)
            logo_file.save(logo_path)

            # Save partner record
            new_partner = Partner(name=name, logo=filename, website=website)
            db.session.add(new_partner)
            db.session.commit()

            flash('Partner added successfully!', 'success')
        else:
            flash('Invalid file type. Allowed: png, jpg, jpeg, gif.', 'danger')

        return redirect(url_for('admin.manage_partners'))

    return render_template('admin/partners.html', partners=partners)


@admin_bp.route('/partners/delete/<int:id>', methods=['POST'])
@login_required
def delete_partner(id):
    """Delete a partner and their logo file"""
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    partner = Partner.query.get_or_404(id)

    # ✅ Remove logo file from uploads folder if it exists
    if partner.logo:
        logo_path = os.path.join(current_app.root_path, 'static', 'uploads', 'partners', partner.logo)
        if os.path.exists(logo_path):
            os.remove(logo_path)

    db.session.delete(partner)
    db.session.commit()

    flash(f"Partner '{partner.name}' deleted successfully.", "success")
    return redirect(url_for('admin.manage_partners'))