"""Password hashing (bcrypt) and stateless JWT handling.

The production stack described in the project doc uses passlib/bcrypt on the
backend; here we call the same bcrypt primitives directly for a smaller,
dependency-light surface. JWT tokens embed the user id and role so admin
enforcement is performed server-side on every request.
"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from config import settings


def hash_password(plain: str) -> str:
    """Hash a plain-text password (returns a self-contained bcrypt string)."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Compare a plain-text password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    """Issue a signed JWT carrying the user id and role."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Validate a JWT and return its payload, or None if invalid/expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None
