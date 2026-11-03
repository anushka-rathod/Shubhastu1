"""
Authentication and security services for Shubhashtu Fashion.
Implements PBKDF2-HMAC-SHA256 password hashing with cryptographic salts.
"""
import hashlib
import secrets
import base64
from datetime import datetime, timedelta

def hash_password(password: str) -> tuple[str, str]:
    """Hashes password with a unique cryptographic salt."""
    salt = secrets.token_hex(16)
    iterations = 100_000
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    password_hash = base64.b64encode(key).decode('utf-8')
    return password_hash, salt

def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verifies a plain text password against stored hash and salt."""
    iterations = 100_000
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    computed_hash = base64.b64encode(key).decode('utf-8')
    return secrets.compare_digest(computed_hash, password_hash)

def generate_reset_token() -> tuple[str, datetime]:
    """Generates a secure password reset token valid for 2 hours."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=2)
    return token, expires_at

def generate_session_id() -> str:
    """Generates a unique session id for guest carts and tracking."""
    return secrets.token_hex(24)

