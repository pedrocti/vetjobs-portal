# routes/admin/__init__.py
from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from . import (
cv_requests,
training_programs,
dashboard,
stats,
verification,
job,
application,
veterans,
employer,
payments,
payment_settings,
analytics,
message,
testimonial,
partners,
admin_settings,
)