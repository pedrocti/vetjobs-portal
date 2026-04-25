from app import db
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from flask_sqlalchemy import SQLAlchemy
from enum import Enum


class PasswordResetToken(db.Model):
  __tablename__ = "password_reset_tokens"

  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)  
  token = db.Column(db.String(64), unique=True, nullable=False, index=True)
  expires_at = db.Column(db.DateTime, nullable=False)
  used = db.Column(db.Boolean, default=False)
  created_at = db.Column(db.DateTime, default=datetime.utcnow)

  # Relationship
  user = db.relationship(
      'User',
      backref=db.backref('password_reset_tokens', lazy=True),
      primaryjoin="User.id==PasswordResetToken.user_id"
  )

  @staticmethod
  def generate_token(user):
      """Generate and store a reset token."""
      import secrets
      # Invalidate existing unused tokens
      PasswordResetToken.query.filter_by(user_id=user.id, used=False).update({"used": True})

      token = secrets.token_urlsafe(32)
      reset_token = PasswordResetToken(
          user_id=user.id,
          token=token,
          expires_at=datetime.utcnow() + timedelta(hours=1)
      )
      db.session.add(reset_token)
      db.session.commit()
      return token

  @staticmethod
  def verify_token(token):
      """Validate reset token and return user if valid."""
      reset_token = PasswordResetToken.query.filter_by(token=token, used=False).first()
      if not reset_token or datetime.utcnow() > reset_token.expires_at:
          return None
      return reset_token.user

  @staticmethod
  def use_token(token):
      """Mark a token as used."""
      reset_token = PasswordResetToken.query.filter_by(token=token).first()
      if reset_token:
          reset_token.used = True
          db.session.commit()
          return True
      return False

  def __repr__(self):
      return f"<PasswordResetToken {self.token[:8]}...>"