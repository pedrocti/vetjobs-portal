from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from extensions import db
from models import User, VeteranProfile
from models.marketplace import ServiceOffer, ServiceRequest, SERVICE_CATEGORIES
from . import admin_bp
from services.email_service import EmailService
from services.notification_service import notification_service
from .stats import get_admin_stats


@admin_bp.route('/marketplace')
@login_required
def marketplace_admin():
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    status_filter = request.args.get('status', 'open')
    category_filter = request.args.get('category', '')

    q = ServiceRequest.query
    if status_filter:
        q = q.filter_by(status=status_filter)
    if category_filter:
        q = q.filter_by(category=category_filter)

    requests_list = q.order_by(ServiceRequest.created_at.desc()).all()

    open_count    = ServiceRequest.query.filter_by(status='open').count()
    matched_count = ServiceRequest.query.filter_by(status='matched').count()
    closed_count  = ServiceRequest.query.filter_by(status='closed').count()
    offers_count  = ServiceOffer.query.filter_by(is_active=True).count()

    stats = get_admin_stats()
    stats.update({
        'open_requests': open_count,
        'matched_requests': matched_count,
        'closed_requests': closed_count,
        'active_offers': offers_count,
    })

    return render_template(
        'admin/marketplace.html',
        requests_list=requests_list,
        categories=SERVICE_CATEGORIES,
        status_filter=status_filter,
        category_filter=category_filter,
        stats=stats,
    )


@admin_bp.route('/marketplace/match', methods=['POST'])
@login_required
def marketplace_match():
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    request_id  = request.form.get('request_id', type=int)
    veteran_id  = request.form.get('veteran_id', type=int)
    admin_notes = request.form.get('admin_notes', '').strip()

    sr = ServiceRequest.query.get_or_404(request_id)
    veteran = User.query.get_or_404(veteran_id)

    sr.matched_veteran_id = veteran_id
    sr.status = 'matched'
    sr.admin_notes = admin_notes
    db.session.commit()

    # Notify matched veteran
    try:
        notification_service.notify_marketplace_match(
            veteran_user=veteran,
            role_needed=sr.role_needed,
            client_name=sr.client_name,
            admin_notes=admin_notes or None
        )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Marketplace match notification failed: {e}")

    # Notify client by email
    try:
        if sr.client_email:
            EmailService().send_marketplace_client_match_email(
                client_email=sr.client_email,
                client_name=sr.client_name,
                role_needed=sr.role_needed,
                veteran_name=veteran.full_name,
                admin_notes=admin_notes or None
            )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Client match email failed: {e}")

    # Notify client by email
    try:
        if sr.client_email:
            EmailService().send_marketplace_client_match_email(
                client_email=sr.client_email,
                client_name=sr.client_name,
                role_needed=sr.role_needed,
                veteran_name=veteran.full_name,
                admin_notes=admin_notes or None
            )
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Client match email failed: {e}")

    flash(
        f'Successfully matched {veteran.full_name} with "{sr.role_needed}" request from {sr.client_name}.',
        'success'
    )
    return redirect(url_for('admin.marketplace_admin'))


@admin_bp.route('/marketplace/request/<int:request_id>/status', methods=['POST'])
@login_required
def marketplace_update_status(request_id):
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    new_status = request.form.get('status', 'open')
    sr = ServiceRequest.query.get_or_404(request_id)
    sr.status = new_status
    db.session.commit()
    flash(f'Request status updated to {new_status}.', 'success')
    return redirect(url_for('admin.marketplace_admin'))


@admin_bp.route('/marketplace/match-form/<int:request_id>')
@login_required
def marketplace_match_form(request_id):
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('main.index'))

    sr = ServiceRequest.query.get_or_404(request_id)

    veterans = (
        db.session.query(User, VeteranProfile)
        .outerjoin(VeteranProfile, User.id == VeteranProfile.user_id)
        .filter(User.user_type == 'veteran')
        .filter(User.active == True)
        .order_by(
            db.case((VeteranProfile.veteran_tier == 'verified', 0), else_=1),
            User.created_at.desc()
        )
        .all()
    )

    service_offers = (
        ServiceOffer.query
        .filter_by(category=sr.category, is_active=True)
        .all()
    )
    offer_user_ids = {o.user_id for o in service_offers}

    stats = get_admin_stats()
    return render_template(
        'admin/marketplace_match.html',
        sr=sr,
        veterans=veterans,
        offer_user_ids=offer_user_ids,
        stats=stats,
    )
