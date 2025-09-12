# app/api/routers/auth.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.services.user_service import (
    authenticate,
    upsert_oauth_user,
    get_by_email,
    mark_email_verified,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    create_email_verification_token,
    decode_email_verification_token,
)
from app.core.config import settings
from app.schemas.user import UserRead
from app.schemas.auth import TokenPair, RefreshRequest, TokenRefresh, VerifyEmailRequest
from app.services.email_service import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/login", response_model=TokenPair)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    # Requiere email verificado (si está habilitado)
    if settings.ENFORCE_EMAIL_VERIFICATION and not user.email_verified:
        token = create_email_verification_token(user.id)
        verify_url = f"{settings.API_BASE_URL}{settings.API_V1_STR}/auth/verify/confirm?token={token}"
        send_verification_email(user.email, verify_url)
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Verification sent.",
        )

    access = create_access_token(subject=user.id)
    refresh = create_refresh_token(subject=user.id)

    # Registrar último acceso
    user.last_login_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserRead.model_validate(user),
    }

@router.post("/refresh", response_model=TokenRefresh)
def refresh_token(payload: RefreshRequest):
    try:
        data = decode_refresh_token(payload.refresh_token)
        user_id = data["sub"]  # UUID str
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    new_access = create_access_token(subject=user_id)
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

# --- Email verification (pedir link) ---
@router.post("/verify/request", status_code=204)
def request_email_verification(
    payload: VerifyEmailRequest,
    db: Session = Depends(get_db),
):
    user = get_by_email(db, payload.email)
    if not user:
        # No revelamos si existe o no el email
        return
    token = create_email_verification_token(user.id)
    verify_url = f"{settings.API_BASE_URL}{settings.API_V1_STR}/auth/verify/confirm?token={token}"
    send_verification_email(user.email, verify_url)
    return

# --- Email verification (confirmar) ---
@router.get("/verify/confirm")
def confirm_email(token: str = Query(...), db: Session = Depends(get_db)):
    try:
        user_id = decode_email_verification_token(token)  # UUID str
    except JWTError:
        raise HTTPException(status_code=400, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email_verified:
        return {"message": "Email already verified"}

    mark_email_verified(db, user)
    return {"message": "Email verified successfully"}

# --- OAuth upsert (intercambio simplificado) ---
@router.post("/oauth/upsert", response_model=TokenPair)
def oauth_upsert(data: dict, db: Session = Depends(get_db)):
    """
    Espera un payload del frontend que ya validó el ID Token con el proveedor (PoC):
    {
      "provider": "google",
      "sub": "provider_subject",
      "email": "user@example.com",
      "full_name": "Name",
      "picture": "https://...",
      "email_verified": true
    }
    """
    required = {"provider", "sub", "email"}
    if not required.issubset(data):
        raise HTTPException(status_code=400, detail="Missing provider/sub/email")

    from app.schemas.user import UserCreateOAuth
    u = UserCreateOAuth(
        email=data["email"],
        full_name=data.get("full_name"),
        oauth_provider=data["provider"],
        oauth_sub=data["sub"],
        oauth_picture=data.get("picture"),
        email_verified_from_provider=bool(data.get("email_verified")),
    )
    user = upsert_oauth_user(db, u)

    # Si pedimos verificación local y el IdP no verificó
    if settings.ENFORCE_EMAIL_VERIFICATION and not user.email_verified:
        token = create_email_verification_token(user.id)
        verify_url = f"{settings.API_BASE_URL}{settings.API_V1_STR}/auth/verify/confirm?token={token}"
        send_verification_email(user.email, verify_url)
        raise HTTPException(
            status_code=403,
            detail="Email not verified. Verification sent.",
        )

    access = create_access_token(subject=user.id)
    refresh = create_refresh_token(subject=user.id)
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": UserRead.model_validate(user),
    }
