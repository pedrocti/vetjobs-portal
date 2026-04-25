# =====================================
# training_programs.py (Cleaned + Safe)
# =====================================
from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, TrainingProgram
from models.review import Review 
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import request, redirect, url_for
from app import db
from models.review import Review
import os


training_bp = Blueprint(
    "training",
    __name__,
    url_prefix="/programs",
    template_folder="templates/training"
)

# -----------------------------
# VIEW ALL PROGRAMS
# -----------------------------
@training_bp.route("/")
def list_programs():
    programs = TrainingProgram.query.filter_by(is_active=True)\
        .order_by(TrainingProgram.created_at.desc()).all()
    return render_template("training/list.html", programs=programs)


# -----------------------------
# VIEW SINGLE PROGRAM
# -----------------------------
@training_bp.route("/<int:program_id>")
def view_program(program_id):
    program = TrainingProgram.query.get_or_404(program_id)

    reviews = Review.query.filter_by(program_id=program.id).all()

    return render_template(
        "training/view_programs.html",
        program=program,
        reviews=reviews
    )


# -----------------------------
# ADD REVIEW
# -----------------------------
@training_bp.route("/<int:program_id>/add-review", methods=["POST"])
def add_review(program_id):
    program = TrainingProgram.query.get_or_404(program_id)

    name = request.form.get("name")
    comment = request.form.get("comment")
    rating = request.form.get("rating")

    if not comment:
        return redirect(url_for("training.view_program", program_id=program.id))

    review = Review(
        program_id=program.id,
        user_name=name,
        rating=int(rating) if rating else None,   # ✅ THIS WAS MISSING
        comment=comment
    )

    db.session.add(review)
    db.session.commit()

    return redirect(url_for("training.view_program", program_id=program.id))