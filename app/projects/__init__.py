from flask import Blueprint

projects = Blueprint('projects', __name__, template_folder='../templates/projects')

from app.projects import routes  # noqa: F401, E402
