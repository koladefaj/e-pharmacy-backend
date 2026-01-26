import logging
import bcrypt
from app.core.exceptions import PasswordVerificationError
from datetime import datetime, timedelta, timezone
from jose import jwt
from app.core.config import settings


# Initialize logger for tracking token generation events
logger = logging.getLogger(__name__)


# ----- JWT --------

def create_access_token(user) -> str:
    """
    Generates a short-lived JWT Access Token.
    
    Payload:
    - sub: The User UUID (Standard subject claim)
    - type: The type which is access token
    - email: Included for quick frontend display without a DB lookup
    - role: The role of the user
    - exp: Expiration timestamp (Default: 20 minutes)
    """

    now = datetime.now(timezone.utc)
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    # Ensure user.id is a string as UUID objects aren't JSON serializable by default
    payload = {
        "sub": str(user.id), 
        "type": "access",
        "email": str(user.email),
        "role": user.role.value,
        "iat": now, 
        "exp": expire
    }
    
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    logger.debug(f"JWT: Access token created for user {user.id}")
    return token

def create_refresh_token(user) -> str:
    """
    Generates a long-lived JWT Refresh Token.
    Used to obtain a new access token without re-entering credentials.
    """

    now = datetime.now(timezone.utc)
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )

    # We add a 'type' claim to prevent refresh tokens from being used as access tokens
    payload = {
        "sub": str(user.id), 
        "type": "refresh",
        "email": str(user.email),
        "role": user.role.value, 
        "iat": now,
        "exp": expire
    }

    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    logger.debug(f"JWT: Refresh token created for user {user.id}")
    return token


# --- HASHING BCRYPT ---

MAX_BYTE_LENGTH = 72

def hash_password(password: str) -> str:
    """Hashes a plain-text password using native Bcrypt."""

    # Ensure UTF-8 byte length check (some emojis/chars are > 1 byte)
    if len(password.encode("utf-8")) > MAX_BYTE_LENGTH:
        logger.warning("Password hashing failed: Input exceeds 72-byte limit.")
        raise PasswordVerificationError("Password too long")

    # hashpw returns bytes, so we decode to utf-8 string for DB storage
    return bcrypt.hashpw(
        password.encode("utf-8"), 
        bcrypt.gensalt()
    ).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against a stored hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), 
            hashed_password.encode("utf-8")
        )
    except Exception as e:
        logger.error(f"Password verification failed due to internal error")
        return False

