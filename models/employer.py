from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum 


class EmployerProfile(db.Model):
  """Employer profile model for company information, verification, and employer preferences."""
  __tablename__ = "employer_profile"

  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)

  # Company Information
  company_name = db.Column(db.String(255), nullable=True)
  company_email = db.Column(db.String(120), nullable=True)
  company_website = db.Column(db.String(200), nullable=True)
  company_logo = db.Column(db.String(255), nullable=True)
  industry = db.Column(db.String(100), nullable=True)
  company_size = db.Column(db.String(50), nullable=True)
  company_address = db.Column(db.Text, nullable=True)
  company_description = db.Column(db.Text, nullable=True)

  # Diversity & Inclusion
  diversity_statement = db.Column(db.Text, nullable=True)

  # Recruiter / HR Information
  recruiter_name = db.Column(db.String(100), nullable=True)
  recruiter_position = db.Column(db.String(100), nullable=True)
  recruiter_email = db.Column(db.String(120), nullable=True)
  recruiter_phone = db.Column(db.String(20), nullable=True)
  hr_contact_email = db.Column(db.String(120), nullable=True)
  hr_linkedin = db.Column(db.String(255), nullable=True)

  # Job Posting Preferences
  hiring_location = db.Column(db.String(200), nullable=True)
  preferred_job_types = db.Column(db.Text, nullable=True)
  work_type = db.Column(db.String(100), nullable=True)
  benefits_offered = db.Column(db.Text, nullable=True)
  salary_currency = db.Column(db.String(10), default='NGN', nullable=False)

  # Verification
  cac_number = db.Column(db.String(50), nullable=True)
  cac_document = db.Column(db.String(255), nullable=True)

  # Status & Verification
  profile_completed = db.Column(db.Boolean, default=False, nullable=False)
  is_verified = db.Column(db.Boolean, default=False, nullable=False)
  verification_status = db.Column(db.String(50), default='pending', nullable=False)
  admin_notes = db.Column(db.Text, nullable=True)
  verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
  verified_at = db.Column(db.DateTime, nullable=True)
  reviewed_at = db.Column(db.DateTime, nullable=True)
  rejection_reason = db.Column(db.Text, nullable=True)

  # Privacy & Subscription
  hide_contact_info = db.Column(db.Boolean, default=False, nullable=False)
  allow_veteran_contact = db.Column(db.Boolean, default=True, nullable=False)
  subscription_active = db.Column(db.Boolean, default=False, nullable=False)
  subscription_plan = db.Column(db.String(50), nullable=True)  # 'starter', 'professional', 'enterprise_plus'
  subscription_expires_at = db.Column(db.DateTime, nullable=True)

  # Timestamps
  created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
  updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

  # Tips
  hiring_tips_sent = db.Column(db.Boolean, default=False, nullable=False)


  # Relationships
  user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('employer_profile', uselist=False))
  verified_by_admin = db.relationship('User', foreign_keys=[verified_by], uselist=False)

  # Helper Methods
  def can_access_veterans(self):
      """Check if employer can access veteran profiles."""
      return bool(self.profile_completed and (self.subscription_active or self.is_trial_active()))

  def is_trial_active(self):
      """Trial period lasts 7 days."""
      if not self.created_at:
          return False
      trial_end = self.created_at + timedelta(days=7)
      return datetime.utcnow() < trial_end

  def __repr__(self):
      return f"<EmployerProfile {self.company_name or 'CompanyPending'}>"