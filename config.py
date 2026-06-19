import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _fix_db_url(url):
    """Railway provides postgres:// but SQLAlchemy 2.x requires postgresql://"""
    if url and url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url


_raw_db_url = os.environ.get('DATABASE_URL')
_db_url = _fix_db_url(_raw_db_url) if _raw_db_url else None
_sqlite_url = 'sqlite:///' + os.path.join(BASE_DIR, 'data', 'tasktracker.db')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = _db_url or _sqlite_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    RATELIMIT_STORAGE_URL = 'memory://'
    RATELIMIT_DEFAULT = '200 per day;50 per hour'
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-change-in-production'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
