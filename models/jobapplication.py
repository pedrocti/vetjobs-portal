from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum



class JobApplication(db.Model):
  """Job application model for veterans applying to job posts."""
  __tablename__ = "job_applications"

  id = db.Column(db.Integer, primary_key=True)
  job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
  veteran_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
  reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))

  # Application content
  cover_letter = db.Column(db.Text, nullable=False)
  resume_file = db.Column(db.String(255), nullable=False)

  # Application status
  status = db.Column(db.String(50), default='pending')  # 'pending', 'reviewed', 'accepted', 'rejected'
  employer_notes = db.Column(db.Text)
  reviewed_at = db.Column(db.DateTime)

  # Timestamps
  created_at = db.Column(db.DateTime, default=datetime.utcnow)
  updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

  # Relationships
  job_post = db.relationship(
      'JobPosting',
      backref=db.backref('applications', lazy=True, cascade='all, delete-orphan')  # 👈 fixed here
  )
  veteran = db.relationship(
      'User',
      foreign_keys=[veteran_id],
      backref=db.backref('job_applications', lazy=True)
  )
  reviewed_by_employer = db.relationship(
      'User',
      foreign_keys=[reviewed_by]
  )

  def __repr__(self):
      return f'<JobApplication veteran_id={self.veteran_id} job_id={self.job_id}>'

  def get_status_display(self):
      statuses = {
          'pending': 'Pending Review',
          'reviewed': 'Under Review',
          'accepted': 'Accepted',
          'rejected': 'Rejected'
      }
      return statuses.get(self.status, self.status.title())

  def get_status_badge_class(self):
      classes = {
          'pending': 'bg-warning text-dark',
          'reviewed': 'bg-info',
          'accepted': 'bg-success',
          'rejected': 'bg-danger'
      }
      return classes.get(self.status, 'bg-secondary')

  def get_status_icon(self):
      icons = {
          'pending': 'fas fa-clock',
          'reviewed': 'fas fa-eye',
          'accepted': 'fas fa-check-circle',
          'rejected': 'fas fa-times-circle'
      }
      return icons.get(self.status, 'fas fa-question-circle')
