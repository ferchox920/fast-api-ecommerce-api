# app/api/deps.py
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenPayload


OAUTH_SCOPES = {
    "admin": "Acceso total de administrador.",
    "users:me": "Acceso al perfil del propio usuario.",
    "products:read": "Permiso para leer productos.",
    "products:write": "Permiso para crear, actualizar y eliminar productos.",
    "purchases:read": "Permiso para leer ordenes de compra.",
    "purchases:write": "Permiso para crear y gestionar ordenes de compra.",
    "orders:read": "Permiso para leer ordenes de venta.",
    "orders:write": "Permiso para crear y gestionar ordenes de venta.",
    "cart:read": "Permiso para leer carritos de compra.",
    "cart:write": "Permiso para gestionar carritos de compra.",
    "questions:read": "Permiso para ver preguntas de productos.",
    "questions:write": "Permiso para crear/gestionar preguntas de productos.",
    "notifications:read": "Permiso para leer notificaciones.",
    "notifications:write": "Permiso para gestionar notificaciones.",
}


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    scopes=OAUTH_SCOPES,
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    scopes=OAUTH_SCOPES,
    auto_error=False,
)


def _decode_token(token: str) -> tuple[TokenPayload, list[str]]:
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    token_data = TokenPayload(**payload)
    token_scopes: list[str] = payload.get("scopes", []) or []
    return token_data, token_scopes


def decode_token_no_db(token: str) -> TokenPayload:
    token_data, _ = _decode_token(token)
    return token_data


def get_current_user(
    security_scopes: SecurityScopes,
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}"'},
    )

    try:
        token_data, token_scopes = _decode_token(token)
    except JWTError:
        raise cred_exc

    if token_data.sub is None:
        raise cred_exc

    user = db.query(User).filter(User.id == token_data.sub).first()
    if user is None:
        raise cred_exc

    if security_scopes.scopes:
        if "admin" not in token_scopes:
            for scope in security_scopes.scopes:
                if scope not in token_scopes:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Not enough permissions",
                        headers={"WWW-Authenticate": f'Bearer scope="{security_scopes.scope_str}"'},
                    )
    return user


def get_optional_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
) -> User | None:
    if not token:
        return None

    try:
        token_data, _ = _decode_token(token)
    except JWTError:
        return None

    if token_data.sub is None:
        return None

    return db.query(User).filter(User.id == token_data.sub).first()


def get_current_active_user(
    current_user: User = Security(get_current_user, scopes=["users:me"])
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if settings.ENFORCE_EMAIL_VERIFICATION and not current_user.email_verified:
        raise HTTPException(status_code=403, detail="Email not verified")
    return current_user


def get_current_admin(
    current_user: User = Security(get_current_user, scopes=["admin"])
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user
