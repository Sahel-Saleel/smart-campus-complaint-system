"""
Application Configuration
Loads settings from environment variables with sensible defaults.
Supports Development, Production, and Testing configurations.
"""

import os
from datetime import timedelta
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()


def _get_bool(key, default=False):
    """Helper to parse boolean environment variables."""
    val = os.environ.get(key, str(default)).lower()
    return val in ('true', '1', 'yes')


def _get_int(key, default=0):
    """Helper to parse integer environment variables."""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


class BaseConfig:
    """Shared configuration across all environments."""

    # --- Flask Core ---
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-insecure-key-change-me')
    TESTING = False

    # --- Database ---
    _raw_db_url = os.environ.get('DATABASE_URL', 'sqlite:///complaint_system.db')
    # Render provides postgres:// which SQLAlchemy requires to be postgresql://
    if _raw_db_url and _raw_db_url.startswith('postgres://'):
        _raw_db_url = _raw_db_url.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = _raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,  # Verify connections before use
    }

    # --- Session ---
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=_get_int('SESSION_LIFETIME_MINUTES', 30)
    )
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # --- Security ---
    MAX_LOGIN_ATTEMPTS = _get_int('MAX_LOGIN_ATTEMPTS', 5)
    ACCOUNT_LOCKOUT_MINUTES = _get_int('ACCOUNT_LOCKOUT_MINUTES', 15)
    PASSWORD_MIN_LENGTH = _get_int('PASSWORD_MIN_LENGTH', 6)
    BCRYPT_LOG_ROUNDS = _get_int('BCRYPT_LOG_ROUNDS', 12)

    # --- Rate Limiting ---
    RATE_LIMIT_PER_MINUTE = _get_int('RATE_LIMIT_PER_MINUTE', 60)

    # --- Logging ---
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/app.log')
    LOG_MAX_BYTES = _get_int('LOG_MAX_BYTES', 10 * 1024 * 1024)  # 10 MB
    LOG_BACKUP_COUNT = _get_int('LOG_BACKUP_COUNT', 5)

    # --- Email (future use) ---
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = _get_int('MAIL_PORT', 587)
    MAIL_USE_TLS = _get_bool('MAIL_USE_TLS', True)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', '')

    # --- OTP (future use) ---
    OTP_LENGTH = _get_int('OTP_LENGTH', 6)
    OTP_EXPIRY_SECONDS = _get_int('OTP_EXPIRY_SECONDS', 300)

    # --- Application Constants ---
    VALID_ROLES = ['student', 'worker', 'admin', 'principal', 'staff']
    DEPARTMENTS = [
        'Electrical/Plumbing',
        'Hostel',
        'Academic/General',
        'Computer Science Engineering',
        'Mechanical Engineering',
        'Civil Engineering',
        'Electrical Engineering',
        'Electronics Engineering',
        'Artificial Intelligence and Data Science'
    ]
    VALID_STATUSES = ['Pending', 'In Progress', 'Resolved']
    VALID_PRIORITIES = ['Low', 'Medium', 'High']
    CONFIDENTIAL_CATEGORIES = ['Ragging', 'Drug Abuse']
    CATEGORY_ROUTING = {
        'Electrical/Plumbing': 'Electrical/Plumbing',
        'Hostel': 'Hostel',
        'Academic/General': 'Academic/General',
        'Ragging': 'Principal',
        'Drug Abuse': 'Principal',
    }


class DevelopmentConfig(BaseConfig):
    """Development-specific settings."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    LOG_LEVEL = 'DEBUG'


class ProductionConfig(BaseConfig):
    """Production-specific settings."""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Requires HTTPS
    SECRET_KEY = os.environ.get('SECRET_KEY', BaseConfig.SECRET_KEY)


class TestingConfig(BaseConfig):
    """Testing-specific settings."""
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SESSION_COOKIE_SECURE = False
    BCRYPT_LOG_ROUNDS = 4  # Faster hashing for tests
    MAX_LOGIN_ATTEMPTS = 100  # Don't lock out during tests


# Configuration map — select via FLASK_ENV environment variable
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
}


def get_config():
    """Get the configuration class based on FLASK_ENV."""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    return config_map.get(env, DevelopmentConfig)
