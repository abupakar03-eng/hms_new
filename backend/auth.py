import bcrypt
import re
from datetime import datetime, timedelta
from typing import Optional, Set
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from . import models, crud
from .database import get_db

# ============================
# Security Configuration
# ============================
SECRET_KEY = "h0spit@l_s3cr3t_k3y_v3ry_s3cur3_2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480   # 8 hours session timeout
REFRESH_TOKEN_EXPIRE_DAYS = 1       # 1 day refresh token

# In-memory token blacklist (revoked tokens)
TOKEN_BLACKLIST: Set[str] = set()

# Failed login tracking: username -> {count, locked_until}
FAILED_LOGINS: dict = {}
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


# ============================
# Password Hashing (bcrypt)
# ============================
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt (cost factor 12 for security)."""
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
    return hashed.decode('utf-8')


def validate_password_strength(password: str) -> bool:
    """Enforce minimum password strength requirements."""
    if len(password) < 8:
        return False
    if not re.search(r'[A-Za-z]', password):
        return False
    return True


# ============================
# Brute Force Protection
# ============================
def check_account_lockout(username: str) -> None:
    """Raise exception if account is locked due to too many failed attempts."""
    if username in FAILED_LOGINS:
        data = FAILED_LOGINS[username]
        if data.get("locked_until") and datetime.utcnow() < data["locked_until"]:
            remaining = int((data["locked_until"] - datetime.utcnow()).total_seconds() / 60) + 1
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account temporarily locked due to {MAX_FAILED_ATTEMPTS} failed attempts. "
                       f"Try again in {remaining} minute(s)."
            )
        # Reset if lockout expired
        if data.get("locked_until") and datetime.utcnow() >= data["locked_until"]:
            FAILED_LOGINS.pop(username, None)


def record_failed_login(username: str) -> None:
    """Record a failed login attempt and lock if threshold exceeded."""
    if username not in FAILED_LOGINS:
        FAILED_LOGINS[username] = {"count": 0, "locked_until": None}
    FAILED_LOGINS[username]["count"] += 1
    if FAILED_LOGINS[username]["count"] >= MAX_FAILED_ATTEMPTS:
        FAILED_LOGINS[username]["locked_until"] = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)


def reset_failed_logins(username: str) -> None:
    """Clear failed login counter on successful login."""
    FAILED_LOGINS.pop(username, None)


# ============================
# JWT Token Management
# ============================
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),   # issued at
        "type": "access"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a longer-lived refresh token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def blacklist_token(token: str) -> None:
    """Add token to blacklist (logout)."""
    TOKEN_BLACKLIST.add(token)


def is_token_blacklisted(token: str) -> bool:
    """Check if token has been revoked."""
    return token in TOKEN_BLACKLIST


# ============================
# Input Sanitization
# ============================
def sanitize_input(value: str) -> str:
    """Remove potential XSS characters from user input."""
    if not value:
        return value
    # Remove HTML tags, script injection attempts
    sanitized = re.sub(r'<[^>]+>', '', value)
    sanitized = re.sub(r'[<>"\']', '', sanitized)
    return sanitized.strip()


def validate_phone(phone: str) -> bool:
    """Validate Indian phone number format."""
    return bool(re.match(r'^[6-9]\d{9}$', phone.replace(' ', '').replace('-', '')))


def validate_aadhaar(aadhaar: str) -> bool:
    """Validate Aadhaar number (12 digits)."""
    return bool(re.match(r'^\d{12}$', aadhaar.replace(' ', '')))


def validate_gst(gst: str) -> bool:
    """Validate Indian GST number format."""
    return bool(re.match(r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$', gst.upper()))


# ============================
# Authentication Dependencies
# ============================
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    """Validate JWT and return current user. Checks blacklist and expiry."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Check if token is blacklisted (logged out)
    if is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type", "access")
        if username is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = crud.get_user_by_username(db, username=username)
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def get_current_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Ensure the current user is an Admin."""
    if current_user.role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient privileges. Admin access required."
        )
    return current_user


def get_token_raw(token: str = Depends(oauth2_scheme)) -> str:
    """Return the raw token string for blacklisting purposes."""
    return token
