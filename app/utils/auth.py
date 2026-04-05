import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser

# ── Config ────────────────────────────────────────────────────────────────────

SECRET_KEY: str = os.getenv(
    "SECRET_KEY", "change-me-in-production-use-a-long-random-string"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ── Password hashing ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Timing-safe comparison via bcrypt — prevents timing attacks."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(subject: str) -> str:
    """
    Mint a signed JWT.
    Claims:
      sub  — username (subject)
      iat  — issued-at (UTC)
      exp  — expiry   (UTC)
      type — "access"
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT.
    Raises HTTP 401 with a specific message for expired vs. invalid tokens.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# ── FastAPI dependency ────────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=True)


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    """
    FastAPI dependency — resolves a Bearer token to an AdminUser row.
    Inject with:  _: AdminUser = Depends(get_current_admin)
    """
    payload = decode_access_token(credentials.credentials)

    username: Optional[str] = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing 'sub'.",
        )

    user = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not user:
        # User was deleted after token was issued
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account no longer exists.",
        )

    return user
