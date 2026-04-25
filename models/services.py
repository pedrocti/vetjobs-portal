from datetime import datetime
from app import db

class CVOptimizationRequest(db.Model):
    __tablename__ = 'cv_optimization_requests'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    cv_file = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='cv_requests')

    def __repr__(self):
        return f'<CVOptimizationRequest {self.id} - {self.status}>'