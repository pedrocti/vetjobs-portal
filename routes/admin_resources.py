from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os
from models import db, Resource

admin_resources_bp = Blueprint('admin_resources', __name__, url_prefix='/admin/resources')

# ===============================
# Upload folder
# ===============================
UPLOAD_FOLDER = 'static/uploads/resources'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ===============================
# List Resources
# ===============================
@admin_resources_bp.route('/')
@login_required
def list_resources():
    """Admin: View all resources"""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.admin'))

    resources = Resource.query.order_by(Resource.created_at.desc()).all()
    return render_template('admin/resources_list.html', resources=resources)


# ===============================
# Add New Resource
# ===============================
@admin_resources_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_resource():
    """Admin: Add a new resource"""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.admin'))

    if request.method == 'POST':
        # Get form data
        title = request.form.get('title')
        description = request.form.get('description')
        category = request.form.get('category')
        link = request.form.get('link')  # internal link (optional)
        external_link = request.form.get('external_link')  # external URL (optional)
        image = request.files.get('image')

        # Handle image upload
        image_url = None
        if image and image.filename:
            filename = secure_filename(image.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            image.save(path)
            image_url = f"/{path}"  # relative path for template display

        # ✅ Create and save new Resource entry
        resource = Resource(
            title=title,
            description=description,
            category=category,
            link=link,
            external_link=external_link,
            image_url=image_url,  # ✅ Added this field
            is_published=True
        )

        db.session.add(resource)
        db.session.commit()

        flash('✅ Resource added successfully!', 'success')
        return redirect(url_for('admin_resources.list_resources'))

    # Render add resource form
    return render_template('admin/add_resource.html')



# ===============================
# Edit Resource
# ===============================
@admin_resources_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_resource(id):
    """Admin: Edit an existing resource"""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.admin'))

    resource = Resource.query.get_or_404(id)

    if request.method == 'POST':
        resource.title = request.form.get('title')
        resource.description = request.form.get('description')
        resource.category = request.form.get('category')
        resource.link = request.form.get('link')
        resource.external_link = request.form.get('external_link')

        # Handle updated image if provided
        image = request.files.get('image')
        if image and image.filename:
            filename = secure_filename(image.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            image.save(path)
            resource.image_url = f"/{path}"

        db.session.commit()
        flash('✅ Resource updated successfully!', 'success')
        return redirect(url_for('admin_resources.list_resources'))

    return render_template('admin/edit_resource.html', resource=resource)


# ===============================
# Delete Resource
# ===============================
@admin_resources_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_resource(id):
    """Admin: Delete a resource"""
    if not current_user.is_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.admin'))

    resource = Resource.query.get_or_404(id)
    db.session.delete(resource)
    db.session.commit()
    flash('🗑️ Resource deleted successfully.', 'success')
    return redirect(url_for('admin_resources.list_resources'))
