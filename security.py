"""
Security Utility Module
Handles password hashing with bcrypt (and Werkzeug fallback/migration),
input sanitization, and secure token generation.
"""

import os
import re
import secrets
import bcrypt
from werkzeug.security import check_password_hash as check_werkzeug_hash

# Read BCRYPT_LOG_ROUNDS from environment / defaults
BCRYPT_LOG_ROUNDS = int(os.environ.get('BCRYPT_LOG_ROUNDS', 12))


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt(rounds=BCRYPT_LOG_ROUNDS)
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_value: str) -> bool:
    """Verify password. Supports bcrypt and Werkzeug pbkdf2/scrypt fallback."""
    if not hashed_value or not password:
        return False

    # Check if it looks like a Werkzeug hash (contains pbkdf2, scrypt, or sha256)
    if hashed_value.startswith(('pbkdf2:', 'scrypt:', 'sha256:')):
        return check_werkzeug_hash(hashed_value, password)

    # Otherwise treat as bcrypt
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed_value.encode('utf-8'))
    except Exception:
        return False


def is_bcrypt_hash(hashed_value: str) -> bool:
    """Check if the given string is a valid bcrypt hash."""
    if not hashed_value:
        return False
    # Bcrypt hashes typically start with $2a$, $2b$, or $2y$ and are 60 chars long
    return hashed_value.startswith(('$2a$', '$2b$', '$2y$')) and len(hashed_value) == 60


def generate_secure_token(length: int = 32) -> str:
    """Generate a secure hex token for CSRF or general use."""
    return secrets.token_hex(length)


def sanitize_input(text: str) -> str:
    """Sanitize HTML inputs to prevent basic XSS attacks."""
    if not text:
        return ""
    # Simple search & replace for HTML tags/scripts
    clean = re.sub(r'<[^>]*>', '', text)
    # Escape quotes and brackets
    clean = clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return clean
