from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AdminUser
from app.schemas import AdminUserResponse, ChangePasswordRequest
from app.utils.auth import get_current_admin, hash_password, verify_password

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── GET /admin/me ─────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=AdminUserResponse,
    summary="Return the currently authenticated admin's profile",
)
def me(current_user: AdminUser = Depends(get_current_admin)):
    """Requires a valid Bearer token."""
    return current_user


# ── POST /admin/change-password ───────────────────────────────────────────────

@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the admin password (admin only)",
)
def change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin),
):
    """
    Verifies the current password before applying the new one.
    The client must re-login after a successful change — existing tokens
    remain technically valid until expiry (stateless JWT trade-off).
    """
    if not verify_password(payload.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must differ from the current password.",
        )

    current_user.password = hash_password(payload.new_password)
    db.commit()
