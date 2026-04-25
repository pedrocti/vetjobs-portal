from flask import Blueprint, render_template, redirect, url_for, flash
from app import db
from models import Testimonial

# Admin Testimonials Blueprint
admin_testimonials_bp = Blueprint('admin_testimonials', __name__, url_prefix='/admin/testimonials')


@admin_testimonials_bp.route('/')
def list_testimonials():
    """List all testimonials for admin management."""
    testimonials = Testimonial.query.order_by(Testimonial.created_at.desc()).all()
    return render_template('admin/testimonials_list.html', testimonials=testimonials)


@admin_testimonials_bp.route('/approve/<int:testimonial_id>')
def approve_testimonial(testimonial_id):
    """Approve a testimonial."""
    testimonial = Testimonial.query.get_or_404(testimonial_id)
    testimonial.is_approved = True
    db.session.commit()
    flash("Testimonial approved successfully!", "success")
    return redirect(url_for('admin_testimonials.list_testimonials'))


@admin_testimonials_bp.route('/disapprove/<int:testimonial_id>')
def disapprove_testimonial(testimonial_id):
    """Disapprove a testimonial."""
    testimonial = Testimonial.query.get_or_404(testimonial_id)
    testimonial.is_approved = False
    db.session.commit()
    flash("Testimonial disapproved successfully!", "warning")
    return redirect(url_for('admin_testimonials.list_testimonials'))


@admin_testimonials_bp.route('/delete/<int:testimonial_id>')
def delete_testimonial(testimonial_id):
    """Delete a testimonial."""
    testimonial = Testimonial.query.get_or_404(testimonial_id)
    db.session.delete(testimonial)
    db.session.commit()
    flash("Testimonial deleted successfully!", "danger")
    return redirect(url_for('admin_testimonials.list_testimonials'))
