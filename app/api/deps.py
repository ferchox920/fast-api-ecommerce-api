# app/api/deps.py
from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import TokenPayload

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    scopes={
        "admin": "Acceso de administrador",
        "products:write": "Permisos de escritura para productos",
        "purchases:write": "Permisos de escritura para compras",
    },
)

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
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_data = TokenPayload(**payload)  # ← soporta scopes opcionales
        token_scopes: list[str] = payload.get("scopes", []) or []
    except JWTError:
        raise cred_exc

    if token_data.sub is None:
        raise cred_exc

    user = db.query(User).filter(User.id == token_data.sub).first()
    if user is None:
        raise cred_exc

    # Si el endpoint requiere scopes, verificarlos (a menos que sea admin total)
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
        # por si el token trae "admin" sin que el usuario lo sea
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin only")
    return current_user
