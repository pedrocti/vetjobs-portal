from flask import Blueprint

payments_bp = Blueprint("payments", __name__)

# import all route files so they register
from . import donations
from . import verification
from . import features
from . import subscription
from . import boosts