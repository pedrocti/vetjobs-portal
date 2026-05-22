"""
routes/admin/referral.py
-------------------------
Admin-only referral link management.

GET  /admin/referral/              → list all links + stats
POST /admin/referral/create        → create a new link
POST /admin/referral/toggle/<id>   → activate / deactivate
POST /admin/referral/delete/<id>   → delete a link
GET  /admin/referral/<id>/detail   → full conversion list for one link
"""

import logging
from datetime import datetime

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app
)
from flask_login import login_required, current_user

from extensions import db
from models.referral import ReferralLink, ReferralConversion

logger = logging.getLogger(__name__)

referral_bp = Blueprint('referral', __name__, url_prefix='/admin/referral')


def _require_admin():
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))
    return None


# ─────────────────────────────────────────────────────────────
# LIST + STATS
# ─────────────────────────────────────────────────────────────

@referral_bp.route('/')
@login_required
def index():
    gate = _require_admin()
    if gate:
        return gate

    links = (ReferralLink.query
             .order_by(ReferralLink.created_at.desc())
             .all())

    # Global totals
    total_conversions = ReferralConversion.query.count()
    total_veterans    = ReferralConversion.query.filter_by(user_type='veteran', is_spouse=False).count()
    total_spouses     = ReferralConversion.query.filter_by(user_type='veteran', is_spouse=True).count()
    total_employers   = ReferralConversion.query.filter_by(user_type='employer').count()

    base_url = current_app.config.get('BASE_URL', request.host_url.rstrip('/'))

    return render_template(
        'admin/referral/index.html',
        links=links,
        base_url=base_url,
        totals={
            'all':      total_conversions,
            'veterans': total_veterans,
            'spouses':  total_spouses,
            'employers': total_employers,
        }
    )


# ─────────────────────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────────────────────

@referral_bp.route('/create', methods=['POST'])
@login_required
def create():
    gate = _require_admin()
    if gate:
        return gate

    campaign    = request.form.get('campaign', '').strip()
    description = request.form.get('description', '').strip() or None
    expires_raw = request.form.get('expires_at', '').strip()

    if not campaign:
        flash('Campaign name is required.', 'error')
        return redirect(url_for('referral.index'))

    expires_at = None
    if expires_raw:
        try:
            expires_at = datetime.strptime(expires_raw, '%Y-%m-%d')
        except ValueError:
            flash('Invalid expiry date format.', 'error')
            return redirect(url_for('referral.index'))

    link = ReferralLink.create(
        campaign=campaign,
        admin_id=current_user.id,
        description=description,
        expires_at=expires_at,
    )

    base_url = current_app.config.get('BASE_URL', request.host_url.rstrip('/'))
    flash(
        f'✅ Referral link created for "{campaign}": {link.full_url(base_url)}',
        'success'
    )
    return redirect(url_for('referral.index'))


# ─────────────────────────────────────────────────────────────
# TOGGLE ACTIVE
# ─────────────────────────────────────────────────────────────

@referral_bp.route('/toggle/<int:link_id>', methods=['POST'])
@login_required
def toggle(link_id):
    gate = _require_admin()
    if gate:
        return gate

    link = ReferralLink.query.get_or_404(link_id)
    link.is_active = not link.is_active
    db.session.commit()

    state = 'activated' if link.is_active else 'deactivated'
    flash(f'Link "{link.campaign}" {state}.', 'info')
    return redirect(url_for('referral.index'))


# ─────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────

@referral_bp.route('/delete/<int:link_id>', methods=['POST'])
@login_required
def delete(link_id):
    gate = _require_admin()
    if gate:
        return gate

    link = ReferralLink.query.get_or_404(link_id)
    campaign = link.campaign
    db.session.delete(link)
    db.session.commit()
    flash(f'Link "{campaign}" deleted.', 'info')
    return redirect(url_for('referral.index'))


# ─────────────────────────────────────────────────────────────
# DETAIL — full conversion list for one link
# ─────────────────────────────────────────────────────────────

@referral_bp.route('/<int:link_id>/detail')
@login_required
def detail(link_id):
    gate = _require_admin()
    if gate:
        return gate

    link = ReferralLink.query.get_or_404(link_id)
    conversions = (ReferralConversion.query
                   .filter_by(link_id=link.id)
                   .order_by(ReferralConversion.registered_at.desc())
                   .all())

    base_url = current_app.config.get('BASE_URL', request.host_url.rstrip('/'))

    return render_template(
        'admin/referral/detail.html',
        link=link,
        conversions=conversions,
        base_url=base_url,
    )


# ─────────────────────────────────────────────────────────────
# COPY URL (returns JSON for clipboard JS)
# ─────────────────────────────────────────────────────────────

@referral_bp.route('/<int:link_id>/url')
@login_required
def get_url(link_id):
    gate = _require_admin()
    if gate:
        return jsonify({'error': 'Forbidden'}), 403

    link = ReferralLink.query.get_or_404(link_id)
    base_url = current_app.config.get('BASE_URL', request.host_url.rstrip('/'))
    return jsonify({'url': link.full_url(base_url), 'code': link.code})