from flask import render_template, request, flash, redirect, url_for
from flask_login import login_required
from app import db
from models import CVOptimizationRequest
from . import admin_bp  

@admin_bp.route('/cv-requests')
@login_required
def cv_requests():
    requests = CVOptimizationRequest.query.order_by(
        CVOptimizationRequest.created_at.desc()
    ).all()
    return render_template('admin/cv_requests.html', requests=requests)

@admin_bp.route('/cv-requests/<int:request_id>/complete', methods=['POST'])
@login_required
def mark_cv_completed(request_id):
    req = CVOptimizationRequest.query.get_or_404(request_id)
    req.status = 'completed'
    db.session.commit()
    flash('Marked as completed.', 'success')
    return redirect(url_for('admin.cv_requests'))

@admin_bp.route('/cv-requests/<int:request_id>/delete', methods=['POST'])
@login_required
def delete_cv_request(request_id):
    req = CVOptimizationRequest.query.get_or_404(request_id)
    db.session.delete(req)
    db.session.commit()
    flash('Request deleted.', 'success')
    return redirect(url_for('admin.cv_requests'))