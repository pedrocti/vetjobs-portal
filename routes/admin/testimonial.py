from flask import render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
import os

from . import admin_bp
from app import db
from models import Testimonial

UPLOAD_FOLDER = 'static/uploads/testimonials'


@admin_bp.route('/testimonials')
@login_required
def manage_testimonials():
    testimonials = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
    return render_template('admin/testimonials/manage.html', testimonials=testimonials)


@admin_bp.route('/testimonials/add', methods=['GET', 'POST'])
@login_required
def add_testimonial():
    if request.method == 'POST':
        name = request.form.get('name')
        user_type = request.form.get('user_type')
        role = request.form.get('role')
        message = request.form.get('message')
        image_file = request.files.get('image')

        filename = None

        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)

            # Ensure folder exists
            os.makedirs(upload_path, exist_ok=True)

            image_path = os.path.join(upload_path, filename)
            image_file.save(image_path)

        testimonial = Testimonial(
            name=name,
            user_type=user_type,
            role=role,
            message=message,
            image=filename,
            is_approved=True
        )

        db.session.add(testimonial)
        db.session.commit()

        flash('Testimonial added successfully!', 'success')
        return redirect(url_for('admin.manage_testimonials'))

    return render_template('admin/testimonials/add.html')


@admin_bp.route('/testimonials/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_testimonial(id):
    testimonial = Testimonial.query.get_or_404(id)

    if request.method == 'POST':
        testimonial.name = request.form.get('name')
        testimonial.user_type = request.form.get('user_type')
        testimonial.role = request.form.get('role')
        testimonial.message = request.form.get('message')

        image_file = request.files.get('image')

        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            upload_path = os.path.join(current_app.root_path, UPLOAD_FOLDER)

            os.makedirs(upload_path, exist_ok=True)

            image_path = os.path.join(upload_path, filename)
            image_file.save(image_path)

            testimonial.image = filename

        db.session.commit()

        flash('Testimonial updated successfully!', 'success')
        return redirect(url_for('admin.manage_testimonials'))

    return render_template('admin/testimonials/edit.html', testimonial=testimonial)


@admin_bp.route('/testimonials/delete/<int:id>', methods=['POST'])
@login_required
def delete_testimonial(id):
    testimonial = Testimonial.query.get_or_404(id)

    db.session.delete(testimonial)
    db.session.commit()

    flash('Testimonial deleted successfully.', 'info')
    return redirect(url_for('admin.manage_testimonials'))