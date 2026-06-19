from flask import Blueprint

owner = Blueprint('owner', __name__)

from app.owner import routes  # noqa: E402, F401
