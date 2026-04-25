from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename 
from app import db
from models import Testimonial
from datetime import datetime
import os

admin_testimonials_bp = Blueprint('admin_testimonials', __name__, url_prefix='/admin/testimonials')

# List all testimonials
@admin_testimonials_bp.route('/')
def list_testimonials():
    testimonials = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
    return render_template('admin/testimonials.html', testimonials=testimonials)

# Add a new testimonial
@admin_testimonials_bp.route('/add', methods=['GET', 'POST'])
def add_testimonial():
    if request.method == 'POST':
        name = request.form['name']
        user_type = request.form['user_type']
        role = request.form['role']
        message = request.form['message']

        # ✅ Handle image upload
        image = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                filename = secure_filename(file.filename)
                upload_path = os.path.join('static/uploads/testimonials', filename)
                file.save(upload_path)
                image = filename

        new_testimonial = Testimonial(
            name=name,
            user_type=user_type,
            role=role,
            message=message,
            image=image,
            is_approved=True,
            created_at=datetime.utcnow()
        )

        db.session.add(new_testimonial)
        db.session.commit()

        flash('New testimonial added successfully!', 'success')
        return redirect(url_for('admin_testimonials.list_testimonials'))

    return render_template('admin/add_testimonial.html')


# Delete a testimonial
@admin_testimonials_bp.route('/delete/<int:id>', methods=['POST'])
def delete_testimonial(id):
    testimonial = Testimonial.query.get_or_404(id)
    db.session.delete(testimonial)
    db.session.commit()
    flash('Testimonial deleted successfully.', 'danger')
    return redirect(url_for('admin_testimonials.list_testimonials'))