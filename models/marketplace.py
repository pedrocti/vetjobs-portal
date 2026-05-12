from extensions import db
from datetime import datetime


SERVICE_CATEGORIES = [
    ('driver',      'Driver / Chauffeur'),
    ('security',    'Security Personnel'),
    ('electrician', 'Electrician'),
    ('technician',  'Technician'),
    ('mechanic',    'Mechanic'),
    ('logistics',   'Logistics Support'),
    ('it',          'IT / Communications'),
    ('other',       'Other'),
]


class ServiceOffer(db.Model):
    __tablename__ = 'service_offers'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category   = db.Column(db.String(50), nullable=False)
    title      = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location   = db.Column(db.String(120))
    availability = db.Column(db.String(120))
    rate_info  = db.Column(db.String(200))
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='service_offers')

    @property
    def category_label(self):
        return dict(SERVICE_CATEGORIES).get(self.category, self.category.title())


class ServiceRequest(db.Model):
    __tablename__ = 'service_requests'

    id           = db.Column(db.Integer, primary_key=True)
    client_name  = db.Column(db.String(150), nullable=False)
    client_email = db.Column(db.String(200), nullable=False)
    client_phone = db.Column(db.String(30))
    category     = db.Column(db.String(50), nullable=False)
    role_needed  = db.Column(db.String(200), nullable=False)
    location     = db.Column(db.String(120))
    duration     = db.Column(db.String(100))
    budget       = db.Column(db.String(100))
    details      = db.Column(db.Text)
    status       = db.Column(db.String(30), default='open')
    matched_veteran_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    admin_notes  = db.Column(db.Text)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    matched_veteran = db.relationship('User', foreign_keys=[matched_veteran_id])

    @property
    def category_label(self):
        return dict(SERVICE_CATEGORIES).get(self.category, self.category.title())

    @property
    def status_display(self):
        return {'open': 'Open', 'matched': 'Matched', 'closed': 'Closed'}.get(self.status, self.status.title())
