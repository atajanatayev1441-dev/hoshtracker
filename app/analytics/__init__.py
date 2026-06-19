from flask import Blueprint

analytics = Blueprint('analytics', __name__, template_folder='../templates/analytics')

from app.analytics import routes  # noqa: F401, E402
