from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models.marketplace import ServiceOffer, ServiceRequest, SERVICE_CATEGORIES

marketplace_bp = Blueprint('marketplace', __name__)


# ══════════════════════════════════════════════
# PUBLIC LANDING PAGE
# ══════════════════════════════════════════════
@marketplace_bp.route('/')
def index():
    categories = SERVICE_CATEGORIES
    offers_by_cat = {}
    for slug, label in categories:
        count = ServiceOffer.query.filter_by(category=slug, is_active=True).count()
        if count:
            offers_by_cat[slug] = count
    total_offers = ServiceOffer.query.filter_by(is_active=True).count()
    return render_template(
        'marketplace/index.html',
        categories=categories,
        offers_by_cat=offers_by_cat,
        total_offers=total_offers,
    )


# ══════════════════════════════════════════════
# BROWSE A CATEGORY
# ══════════════════════════════════════════════
@marketplace_bp.route('/browse/<category>')
def browse(category):
    cat_label = dict(SERVICE_CATEGORIES).get(category, category.title())
    offers = (
        ServiceOffer.query
        .filter_by(category=category, is_active=True)
        .order_by(ServiceOffer.created_at.desc())
        .all()
    )
    return render_template(
        'marketplace/browse.html',
        offers=offers,
        category=category,
        cat_label=cat_label,
        categories=SERVICE_CATEGORIES,
    )


# ══════════════════════════════════════════════
# VETERAN: OFFER A SERVICE (GET)
# ══════════════════════════════════════════════
@marketplace_bp.route('/offer')
@login_required
def offer_service():
    if not current_user.is_veteran():
        flash('Only veterans can offer services on this marketplace.', 'warning')
        return redirect(url_for('marketplace.index'))
    existing = ServiceOffer.query.filter_by(user_id=current_user.id, is_active=True).all()
    return render_template(
        'marketplace/offer_form.html',
        categories=SERVICE_CATEGORIES,
        existing=existing,
    )


# ══════════════════════════════════════════════
# VETERAN: SUBMIT OFFER (POST)
# ══════════════════════════════════════════════
@marketplace_bp.route('/offer', methods=['POST'])
@login_required
def submit_offer():
    if not current_user.is_veteran():
        flash('Only veterans can offer services.', 'warning')
        return redirect(url_for('marketplace.index'))

    category     = request.form.get('category', '').strip()
    title        = request.form.get('title', '').strip()
    description  = request.form.get('description', '').strip()
    location     = request.form.get('location', '').strip()
    availability = request.form.get('availability', '').strip()
    rate_info    = request.form.get('rate_info', '').strip()

    if not category or not title:
        flash('Category and title are required.', 'danger')
        return redirect(url_for('marketplace.offer_service'))

    offer = ServiceOffer(
        user_id=current_user.id,
        category=category,
        title=title,
        description=description,
        location=location,
        availability=availability,
        rate_info=rate_info,
    )
    db.session.add(offer)
    db.session.commit()
    flash('Your service offer has been listed! Our team will contact you when there is a match.', 'success')
    return redirect(url_for('marketplace.offer_service'))


# ══════════════════════════════════════════════
# VETERAN: DELETE AN OFFER
# ══════════════════════════════════════════════
@marketplace_bp.route('/offer/<int:offer_id>/delete', methods=['POST'])
@login_required
def delete_offer(offer_id):
    offer = ServiceOffer.query.get_or_404(offer_id)
    if offer.user_id != current_user.id:
        flash('Permission denied.', 'danger')
        return redirect(url_for('marketplace.offer_service'))
    offer.is_active = False
    db.session.commit()
    flash('Offer removed.', 'info')
    return redirect(url_for('marketplace.offer_service'))


# ══════════════════════════════════════════════
# PUBLIC: REQUEST VERIFIED PERSONNEL (GET)
# ══════════════════════════════════════════════
@marketplace_bp.route('/request')
def request_personnel():
    return render_template(
        'marketplace/request_form.html',
        categories=SERVICE_CATEGORIES,
    )


# ══════════════════════════════════════════════
# PUBLIC: SUBMIT REQUEST (POST)
# ══════════════════════════════════════════════
@marketplace_bp.route('/request', methods=['POST'])
def submit_request():
    client_name  = request.form.get('client_name', '').strip()
    client_email = request.form.get('client_email', '').strip()
    client_phone = request.form.get('client_phone', '').strip()
    category     = request.form.get('category', '').strip()
    role_needed  = request.form.get('role_needed', '').strip()
    location     = request.form.get('location', '').strip()
    duration     = request.form.get('duration', '').strip()
    budget       = request.form.get('budget', '').strip()
    details      = request.form.get('details', '').strip()

    if not client_name or not client_email or not role_needed or not category:
        flash('Please fill in all required fields.', 'danger')
        return redirect(url_for('marketplace.request_personnel'))

    req = ServiceRequest(
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        category=category,
        role_needed=role_needed,
        location=location,
        duration=duration,
        budget=budget,
        details=details,
    )
    db.session.add(req)
    db.session.commit()
    flash('Request submitted! Our team will reach out within 24 hours with a matched veteran.', 'success')
    return redirect(url_for('marketplace.index'))
