from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum


# --- Partners (site partners / sponsors) ---
class Partner(db.Model):
    __tablename__ = "partners"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    # store path relative to static/uploads, e.g. "partners/logo.png"
    logo = db.Column(db.String(255), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Partner {self.name}>"


class TrainingProgram (db.Model):
    __tablename__ = "training_programs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    provider = db.Column(db.String(255), nullable=True)  
    link = db.Column(db.String(255), nullable=True)
    image = db.Column(db.String(255), nullable=True)
    tier = db.Column(db.String(50), nullable=True)
    price = db.Column(db.Numeric(10, 2), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    location = db.Column(db.String(255), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default="pending")
    is_featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ New fields
    program_type = db.Column(db.String(100), nullable=True)  
    certification = db.Column(db.String(255), nullable=True)
    duration = db.Column(db.String(100), nullable=True)
    how_to_apply = db.Column(db.Text, nullable=True)
    whatsapp_link = db.Column(db.String(255), nullable=True)

    contact_email = db.Column(db.String(255), nullable=True)
    contact_phone = db.Column(db.String(50), nullable=True)
    facebook_link = db.Column(db.String(255), nullable=True)
    instagram_link = db.Column(db.String(255), nullable=True)
    linkedin_link = db.Column(db.String(255), nullable=True)
    twitter_link = db.Column(db.String(255), nullable=True)
    tiktok_link = db.Column(db.String(255), nullable=True)

    sharable_link = db.Column(db.String(255), unique=True)

    # Relationship
    applications = db.relationship("TrainingApplication", back_populates="program", lazy=True)

    def __repr__(self):
        return f"<TrainingProgram {self.title}>"


class TrainingApplication(db.Model):
    __tablename__ = "training_applications"

    id = db.Column(db.Integer, primary_key=True)
    veteran_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    program_id = db.Column(db.Integer, db.ForeignKey('training_programs.id'), nullable=False)
    message = db.Column(db.Text)
    status = db.Column(db.String(50), default="Pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    program = db.relationship('TrainingProgram', back_populates='applications')

    def __repr__(self):
        return f"<TrainingApplication Veteran:{self.veteran_id} Program:{self.program_id}>"