import os
from datetime import datetime
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, TrainingProgram
from routes.admin import admin_bp  
from flask import render_template
from models import TrainingProgram
from . import admin_bp  

# ----------------------------
# List Programs
# ----------------------------
@admin_bp.route('/program')
@login_required
def programs_list():
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    programs = TrainingProgram.query.order_by(TrainingProgram.created_at.desc()).all()
    return render_template('admin/programs_list.html', programs=programs)


# ----------------------------
# Create Program
# ----------------------------
@admin_bp.route('/program/create', methods=['GET', 'POST'])
@login_required
def create_program():
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        try:
            # Helper to parse dates
            def parse_date(value):
                return datetime.strptime(value, "%Y-%m-%d") if value else None

            data = request.form

            program = TrainingProgram(
                title=data.get('title'),
                description=data.get('description'),
                provider=data.get('provider'),
                location=data.get('location'),
                start_date=parse_date(data.get('start_date')),
                end_date=parse_date(data.get('end_date')),
                link=data.get('link'),  # ✅ FIXED
                program_type=data.get('program_type'),
                certification=data.get('certification'),
                duration=data.get('duration'),
                how_to_apply=data.get('how_to_apply'),
                price=float(data.get('price') or 0.0),
                contact_email=data.get('contact_email'),
                contact_phone=data.get('contact_phone'),
                whatsapp_link=data.get('whatsapp_link'),
                facebook_link=data.get('facebook_link'),
                instagram_link=data.get('instagram_link'),
                linkedin_link=data.get('linkedin_link'),
                twitter_link=data.get('twitter_link'),
                tiktok_link=data.get('tiktok_link'),
                sharable_link=data.get('sharable_link') or None,
                status='approved',
                is_featured=bool(data.get('is_featured')),
                is_active=True,
                created_at=datetime.utcnow()
            )

            # Handle image upload
            image_file = request.files.get("image")
            if image_file and image_file.filename:
                filename = secure_filename(image_file.filename)
                upload_dir = os.path.join("static", "uploads", "training")
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                image_file.save(file_path)
                program.image = f"uploads/training/{filename}"

            db.session.add(program)
            db.session.commit()

            flash("Training program created successfully.", "success")
            return redirect(url_for('admin.programs_list'))

        except Exception as e:
            db.session.rollback()
            print("ERROR CREATING PROGRAM:", str(e))
            flash(f"Error: {str(e)}", "danger")

    return render_template('admin/program_create.html')

@admin_bp.route('/program/edit/<int:program_id>', methods=['GET', 'POST'])
@login_required
def edit_program(program_id):
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    program = TrainingProgram.query.get_or_404(program_id)

    if request.method == 'POST':
        try:
            def parse_date(value):
                return datetime.strptime(value, "%Y-%m-%d") if value else None

            data = request.form

            program.title = data.get('title')
            program.description = data.get('description')
            program.provider = data.get('provider')
            program.location = data.get('location')
            program.start_date = parse_date(data.get('start_date'))
            program.end_date = parse_date(data.get('end_date'))
            program.link = data.get('link')
            program.program_type = data.get('program_type')
            program.certification = data.get('certification')
            program.duration = data.get('duration')
            program.how_to_apply = data.get('how_to_apply')
            program.price = float(data.get('price') or 0.0)
            program.contact_email = data.get('contact_email')
            program.contact_phone = data.get('contact_phone')

            db.session.commit()

            flash("Program updated successfully.", "success")
            return redirect(url_for('admin.programs_list'))

        except Exception as e:
            db.session.rollback()
            print("ERROR UPDATING PROGRAM:", str(e))
            flash("Error updating program.", "danger")

    return render_template('admin/program_create.html', program=program)


@admin_bp.route('/program/delete/<int:program_id>', methods=['POST'])
@login_required
def delete_program(program_id):
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    program = TrainingProgram.query.get_or_404(program_id)

    db.session.delete(program)
    db.session.commit()

    flash("Program deleted successfully.", "success")
    return redirect(url_for('admin.programs_list'))


# ----------------------------
# View Program
# ----------------------------
@admin_bp.route('/program/<int:program_id>')
@login_required
def view_program(program_id):
    if current_user.user_type != 'admin':
        flash("Access denied.", "danger")
        return redirect(url_for('admin.dashboard'))

    program = TrainingProgram.query.get_or_404(program_id)
    return render_template('admin/program_details.html', program=program)


