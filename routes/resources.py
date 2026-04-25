from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash
from models import Resource
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

resources_bp = Blueprint("resources", __name__, url_prefix="/resources")

@resources_bp.route("/")
def all_resources():
    """Show all published resources"""
    resources = Resource.query.filter_by(is_published=True).order_by(Resource.created_at.desc()).all()
    return render_template("resources/all_resources.html", resources=resources)

@resources_bp.route("/<string:category>")
def by_category(category):
    """Show resources filtered by category"""
    valid_categories = ["career", "interview", "networking", "resume"]
    if category not in valid_categories:
        return render_template("404.html"), 404

    resources = Resource.query.filter_by(category=category, is_published=True).order_by(Resource.created_at.desc()).all()
    return render_template("resources/category.html", resources=resources, category=category)

@resources_bp.route("/view/<int:id>")
def view_resource(id):
    """Show a single resource article"""
    resource = Resource.query.get_or_404(id)
    return render_template("resources/view.html", resource=resource)


from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from io import BytesIO

@resources_bp.route('/resume-builder', methods=['GET', 'POST'])
def resume_builder():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        bio = request.form.get('bio')
        summary = request.form.get('summary')
        education = request.form.get('education')
        experience = request.form.get('experience')
        skills = request.form.get('skills')
        template = request.form.get('template', 'classic')
        review_requested = request.form.get('review') == 'yes'

        # 🎯 Handle paid options
        if template == "modern":
            amount = 2000
            feature = f"resume_template_modern_{name}"
            flash("✨ Redirecting to payment for Modern Resume Template (₦2000)...", "info")
            return redirect(url_for('payments.init_payment', feature=feature, amount=amount))

        elif review_requested:
            amount = 5000
            feature = f"resume_review_{name}"
            flash("💼 Redirecting to payment for Professional Resume Review (₦5000)...", "info")
            return redirect(url_for('payments.init_payment', feature=feature, amount=amount))

        # 🧾 Free resume generation (Classic)
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        title_style = styles['Title']
        section_title = styles['Heading2']

        elements.append(Paragraph(f"<b><font size=16>{name}</font></b>", title_style))
        elements.append(Paragraph(f"{email} | {phone}", styles['Normal']))
        if address:
            elements.append(Paragraph(address, styles['Normal']))
        elements.append(Spacer(1, 12))

        if bio:
            elements.append(Paragraph("<b>Bio</b>", section_title))
            elements.append(Paragraph(bio.replace("\n", "<br/>"), styles['Normal']))
            elements.append(Spacer(1, 12))

        if summary:
            elements.append(Paragraph("<b>Professional Summary</b>", section_title))
            elements.append(Paragraph(summary.replace("\n", "<br/>"), styles['Normal']))
            elements.append(Spacer(1, 12))

        if education:
            elements.append(Paragraph("<b>Education</b>", section_title))
            elements.append(Paragraph(education.replace("\n", "<br/>"), styles['Normal']))
            elements.append(Spacer(1, 12))

        if experience:
            elements.append(Paragraph("<b>Work Experience</b>", section_title))
            elements.append(Paragraph(experience.replace("\n", "<br/>"), styles['Normal']))
            elements.append(Spacer(1, 12))

        if skills:
            elements.append(Paragraph("<b>Skills</b>", section_title))
            elements.append(Paragraph(skills.replace(",", " • "), styles['Normal']))

        doc.build(elements)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"{name.replace(' ', '_')}_resume_classic.pdf",
            mimetype="application/pdf"
        )

    return render_template('resources/resume_builder.html')
