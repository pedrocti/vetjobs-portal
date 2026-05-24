import json
from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from . import admin_bp
from app import db
from models import User

PERMISSIONS = [
    ("users",    "Users",    "Veterans & Employers"),
    ("jobs",     "Jobs",     "Job Review, Applications, AI Pipeline"),
    ("content",  "Content",  "Messages, Testimonials, Training, Partners, Resources"),
    ("payments", "Payments", "Payments & Pricing"),
    ("system",   "System",   "Verifications, Email Settings, Platform"),
]

@admin_bp.route("/subadmins")
@login_required
def subadmins():
    if not current_user.is_admin():
        flash("Access denied. Administrators only.", "error")
        return redirect(url_for("main.index"))
    subadmin_list = User.query.filter_by(user_type="subadmin").order_by(User.created_at.desc()).all()
    return render_template("admin/subadmins.html", subadmins=subadmin_list, permissions=PERMISSIONS)

@admin_bp.route("/subadmins/create", methods=["POST"])
@login_required
def create_subadmin():
    if not current_user.is_admin():
        flash("Access denied.", "error")
        return redirect(url_for("main.index"))
    first_name = request.form.get("first_name", "").strip()
    last_name  = request.form.get("last_name", "").strip()
    username   = request.form.get("username", "").strip()
    email      = request.form.get("email", "").strip()
    password   = request.form.get("password", "").strip()
    if not all([first_name, last_name, username, email, password]):
        flash("All fields are required.", "error")
        return redirect(url_for("admin.subadmins"))
    if User.query.filter_by(email=email).first():
        flash("A user with that email already exists.", "error")
        return redirect(url_for("admin.subadmins"))
    if User.query.filter_by(username=username).first():
        flash("That username is already taken.", "error")
        return redirect(url_for("admin.subadmins"))
    perms = {}
    for perm, _, _ in PERMISSIONS:
        perms[perm] = request.form.get(f"perm_{perm}") == "on"
    user = User(
        first_name=first_name,
        last_name=last_name,
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        user_type="subadmin",
        active=True,
        is_verified=True,
    )
    user.set_permissions(perms)
    db.session.add(user)
    db.session.commit()
    flash(f"Subadmin {username} created successfully.", "success")
    return redirect(url_for("admin.subadmins"))

@admin_bp.route("/subadmins/<int:user_id>/delete", methods=["POST"])
@login_required
def delete_subadmin(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "error")
        return redirect(url_for("main.index"))
    user = User.query.get_or_404(user_id)
    if user.user_type != "subadmin":
        flash("That is not a subadmin account.", "error")
        return redirect(url_for("admin.subadmins"))
    db.session.delete(user)
    db.session.commit()
    flash(f"Subadmin {user.username} removed.", "success")
    return redirect(url_for("admin.subadmins"))

@admin_bp.route("/subadmins/<int:user_id>/permissions", methods=["POST"])
@login_required
def update_subadmin_permissions(user_id):
    if not current_user.is_admin():
        flash("Access denied.", "error")
        return redirect(url_for("main.index"))
    user = User.query.get_or_404(user_id)
    if user.user_type != "subadmin":
        flash("That is not a subadmin account.", "error")
        return redirect(url_for("admin.subadmins"))
    perms = {}
    for perm, _, _ in PERMISSIONS:
        perms[perm] = request.form.get(f"perm_{perm}") == "on"
    user.set_permissions(perms)
    db.session.commit()
    flash(f"Permissions updated for {user.username}.", "success")
    return redirect(url_for("admin.subadmins"))
