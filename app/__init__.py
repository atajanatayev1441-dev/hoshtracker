import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к странице.'
login_manager.login_message_category = 'warning'


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(data_dir, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from app.auth import auth as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.tasks import tasks as tasks_bp
    app.register_blueprint(tasks_bp, url_prefix='/tasks')

    from app.admin import admin as admin_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')

    from app.projects import projects as projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')

    from app.analytics import analytics as analytics_bp
    app.register_blueprint(analytics_bp, url_prefix='/analytics')

    from app.api import api as api_bp
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    csrf.exempt(api_bp)

    from app import models  # noqa: F401

    from flask import redirect, url_for
    from flask_login import current_user

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('tasks.dashboard'))
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_globals():
        from flask_login import current_user as cu
        unread = 0
        if cu.is_authenticated:
            unread = cu.unread_notification_count()
        return {'Task': models.Task, 'unread_count': unread}

    return app
