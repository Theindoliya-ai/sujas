import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser
from app.schemas import AdminUserCreate, AdminUserResponse, LoginRequest, TokenResponse
from app.utils.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)

router = APIRouter(tags=["Authentication"])

# Guard: first-time registration requires this env flag to be set.
# Set ALLOW_REGISTER=1 in .env before running setup, then unset it.
_ALLOW_REGISTER = os.getenv("ALLOW_REGISTER", "0") == "1"


# ── POST /register ────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=AdminUserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register the initial admin account",
)
def register(payload: AdminUserCreate, db: Session = Depends(get_db)):
    """
    One-time registration endpoint.

    Allowed only when **both** conditions are true:
    - `ALLOW_REGISTER=1` is set in the environment
    - No admin user exists yet

    Remove `ALLOW_REGISTER` from `.env` after the first admin is created.
    """
    if not _ALLOW_REGISTER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Set ALLOW_REGISTER=1 to enable.",
        )
    if db.query(AdminUser).count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An admin account already exists.",
        )

    existing = db.query(AdminUser).filter(AdminUser.username == payload.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken.",
        )

    user = AdminUser(username=payload.username, password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ── POST /login ───────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Admin login — returns a JWT Bearer token",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticates with username + password and returns a signed JWT.

    **Usage:**
    ```
    Authorization: Bearer <access_token>
    ```

    The token is valid for `expires_in` seconds (default: 3600).

    **Security note:** Both "user not found" and "wrong password" return the
    same `401` response to prevent username enumeration.
    """
    user = db.query(AdminUser).filter(AdminUser.username == payload.username).first()

    # Always call verify_password even on a dummy hash so response time is
    # constant whether the username exists or not (timing-safe).
    _dummy_hash = "$2b$12$KIXfakehashjustfortimingXXXXXXXXXXXXXXXXXXXXXXXXXX"
    password_ok = verify_password(
        payload.password,
        user.password if user else _dummy_hash,
    )

    if not user or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=user.username)
    return TokenResponse(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
