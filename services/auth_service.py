"""
Authentication and security services for Shubhashtu Fashion.
Implements PBKDF2-HMAC-SHA256 password hashing with cryptographic salts,
HMAC-SHA256 signed cookie security, and time-expiring reset tokens.
"""
import hmac
import hashlib
import secrets
import base64
import time
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

# ==================== CRYPTOGRAPHIC SIGNED COOKIE HELPERS ====================

def sign_cookie(data: str, secret: str) -> str:
    """
    Cryptographically signs a cookie value using HMAC-SHA256.
    Format: <data>|<timestamp>|<signature>
    Prevents any client-side cookie tampering or identity spoofing.
    """
    ts = str(int(time.time()))
    payload = f"{data}|{ts}"
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}|{signature}"

def verify_signed_cookie(signed_cookie: str, secret: str, max_age_seconds: int = 1209600) -> str | None:
    """
    Verifies the cryptographic signature and timestamp of a signed cookie.
    Returns original data if valid and unexpired; returns None if tampered or expired.
    """
    if not signed_cookie or '|' not in signed_cookie:
        return None
    parts = signed_cookie.split('|')
    if len(parts) != 3:
        return None
    data, ts_str, signature = parts
    try:
        ts = int(ts_str)
        now = int(time.time())
        # Check expiration (default: 14 days)
        if now - ts > max_age_seconds or ts > now + 300: # allow 5 min clock skew
            return None
    except ValueError:
        return None

    expected_payload = f"{data}|{ts_str}"
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        expected_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if secrets.compare_digest(expected_sig, signature):
        return data
    return None

def generate_signed_reset_token(email: str, secret: str) -> str:
    """Generates a signed, time-limited token for password reset."""
    ts = str(int(time.time()))
    payload = f"{email.lower().strip()}|{ts}"
    signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}|{signature}"

def verify_signed_reset_token(token: str, secret: str, max_age_seconds: int = 3600) -> str | None:
    """
    Verifies a signed password reset token.
    Valid for 1 hour by default. Returns email if valid, None if invalid/expired.
    """
    if not token or '|' not in token:
        return None
    parts = token.split('|')
    if len(parts) != 3:
        return None
    email, ts_str, signature = parts
    try:
        ts = int(ts_str)
        now = int(time.time())
        if now - ts > max_age_seconds or ts > now + 300:
            return None
    except ValueError:
        return None

    expected_payload = f"{email}|{ts_str}"
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        expected_payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if secrets.compare_digest(expected_sig, signature):
        return email
    return None


