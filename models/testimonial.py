from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum


class Testimonial(db.Model):
    """Testimonials from veterans or employers."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)  # Person’s name
    user_type = db.Column(db.String(50))  # 'veteran' or 'employer'
    role = db.Column(db.String(120))  # e.g., 'Software Engineer', 'HR Manager'
    message = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(255))  # filename of image (stored in static/uploads/testimonials)
    is_approved = db.Column(db.Boolean, default=True)  # show on site or not
    created_at = db.Column(db.DateTime, default=datetime.utcnow)