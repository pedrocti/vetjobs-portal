from flask import Blueprint, render_template, request, flash, redirect, url_for
from models import db, Partner, Testimonial
from flask_login import current_user

main_bp = Blueprint('main', __name__)


# ===============================
# Homepage
# ===============================
@main_bp.route('/')
def index():
    partners = Partner.query.filter_by(is_active=True).order_by(
        Partner.sort_order, Partner.created_at.desc()
    ).all()

    testimonials = Testimonial.query.filter_by(is_approved=True).order_by(
        Testimonial.created_at.desc()
    ).limit(3).all()

    return render_template(
        'index.html',
        partners=partners,
        testimonials=testimonials
    )


# ===============================
# Static Pages
# ===============================
@main_bp.route('/about')
def about():
    return render_template('about.html')


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        flash("Thank you! Your message has been sent successfully.", "success")
        return redirect(url_for('main.contact'))

    return render_template('contact.html')


# ===============================
# Redirect Helpers
# ===============================
@main_bp.route('/jobs')
def jobs():
    return redirect(url_for('jobs.job_board'))


# ===============================
# Audience Pages
# ===============================
@main_bp.route('/veterans')
def veterans():
    return render_template('veterans.html')


@main_bp.route('/employers')
def employers():
    return render_template('employers.html')


# ===============================
# Testimonials
# ===============================
@main_bp.route('/testimonials')
def testimonials():
    testimonials = Testimonial.query.filter_by(
        is_approved=True
    ).order_by(
        Testimonial.created_at.desc()
    ).all()

    return render_template(
        'testimonials.html',
        testimonials=testimonials
    )


# ===============================
# Programs (Career Events / Alumni / Training)
# ===============================
@main_bp.route('/programs')
def programs():
    return render_template('training/programs.html')


# ===============================
# Services
# ===============================
@main_bp.route('/services')
def services():
    return render_template('services.html')

# ===============================
# Payment Result Pages
# ===============================
@main_bp.route('/payment/success')
def success():
    return render_template('payments/success.html')


@main_bp.route('/payment/failed')
def payment_failed():
    return render_template('payments/failed.html')