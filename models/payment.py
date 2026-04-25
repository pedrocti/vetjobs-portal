from app import db
from datetime import datetime

class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Payment details
    reference = db.Column(db.String(255), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='NGN')

    # Payment type and description
    payment_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    
    # Donation-specific fields
    donor_email = db.Column(db.String(120), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=True)

    # Payment status
    status = db.Column(db.String(50), default="pending")
    paystack_status = db.Column(db.String(50))
    gateway_reference = db.Column(db.String(255))
    paystack_reference = db.Column(db.String(255))

    # Paystack transaction details (optional)
    paystack_transaction_id = db.Column(db.String(100))
    paystack_authorization_code = db.Column(db.String(100))
    paystack_customer_code = db.Column(db.String(100))

    # Payment method
    payment_method = db.Column(db.String(50))  # e.g., 'card', 'bank_transfer'
    channel = db.Column(db.String(50))  # e.g., Paystack channel

    # Metadata & timestamps
    payment_metadata = db.Column(db.JSON)
    paid_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('payments', lazy=True))

    def __repr__(self):
        return f'<Payment {self.reference} - ₦{self.amount}>'

    @property
    def formatted_amount(self):
        return f"₦{self.amount:,.2f}" if self.amount else "₦0.00"

    def is_successful(self):
        return self.status == 'success'