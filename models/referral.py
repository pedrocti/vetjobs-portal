"""
models/referral.py
------------------
Referral link system for admin-generated tracking links.

Two tables:
  ReferralLink  — the link itself (campaign name, code, who created it)
  ReferralClick — one row per registration that came through a link
                  (user_type, is_spouse, timestamp)
"""

from extensions import db
from datetime import datetime
import secrets
import string


def _generate_code(length=8):
    """URL-safe random code, e.g. 'Xk9mP2qR'"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class ReferralLink(db.Model):
    __tablename__ = 'referral_links'

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(20), unique=True, nullable=False, index=True)
    campaign    = db.Column(db.String(150), nullable=False)   # e.g. "LinkedIn May 2026"
    description = db.Column(db.Text, nullable=True)           # optional notes
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_active   = db.Column(db.Boolean, default=True, nullable=False)
    expires_at  = db.Column(db.DateTime, nullable=True)       # None = never expires

    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow, nullable=False)

    # Relationships
    creator      = db.relationship('User', foreign_keys=[created_by],
                                   backref=db.backref('referral_links', lazy='dynamic'))
    conversions  = db.relationship('ReferralConversion', back_populates='link',
                                   lazy='dynamic', cascade='all, delete-orphan')

    # ── Helpers ──────────────────────────────────────────────

    @classmethod
    def create(cls, campaign: str, admin_id: int,
               description: str = None, expires_at=None) -> 'ReferralLink':
        code = _generate_code()
        while cls.query.filter_by(code=code).first():
            code = _generate_code()          # ensure uniqueness

        link = cls(
            code=code,
            campaign=campaign,
            description=description,
            created_by=admin_id,
            expires_at=expires_at,
        )
        db.session.add(link)
        db.session.commit()
        return link

    def full_url(self, base_url: str) -> str:
        return f"{base_url.rstrip('/')}/auth/register?ref={self.code}"

    def is_valid(self) -> bool:
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True

    # ── Stats ─────────────────────────────────────────────────

    @property
    def total(self):
        return self.conversions.count()

    @property
    def veterans(self):
        return self.conversions.filter_by(user_type='veteran', is_spouse=False).count()

    @property
    def spouses(self):
        return self.conversions.filter_by(user_type='veteran', is_spouse=True).count()

    @property
    def employers(self):
        return self.conversions.filter_by(user_type='employer').count()

    def breakdown(self):
        return {
            'total':     self.total,
            'veterans':  self.veterans,
            'spouses':   self.spouses,
            'employers': self.employers,
        }

    def __repr__(self):
        return f'<ReferralLink {self.code!r} campaign={self.campaign!r}>'


class ReferralConversion(db.Model):
    """One row for every user who registered via a referral link."""
    __tablename__ = 'referral_conversions'

    id          = db.Column(db.Integer, primary_key=True)
    link_id     = db.Column(db.Integer, db.ForeignKey('referral_links.id'),
                            nullable=False, index=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'),
                            nullable=False, unique=True)   # one conversion per user
    user_type   = db.Column(db.String(20), nullable=False)  # 'veteran' or 'employer'
    is_spouse   = db.Column(db.Boolean, default=False, nullable=False)
    registered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    link = db.relationship('ReferralLink', back_populates='conversions')
    user = db.relationship('User', foreign_keys=[user_id],
                           backref=db.backref('referral_conversion', uselist=False))

    def __repr__(self):
        return f'<ReferralConversion user={self.user_id} link={self.link_id}>'