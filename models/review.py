from app import db
from datetime import datetime, timedelta

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('training_programs.id'), nullable=False)
    user_name = db.Column(db.String(120))
    rating = db.Column(db.Integer)   
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    program = db.relationship('TrainingProgram', backref=db.backref('reviews', lazy=True))