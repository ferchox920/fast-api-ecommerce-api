# app/services/user_service.py
from sqlalchemy.orm import Session
from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserCreateOAuth, UserUpdate

def get_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, data: UserCreate) -> User:
    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=get_password_hash(data.password),
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        country=data.country,
        phone=data.phone,
        birthdate=data.birthdate,
        avatar_url=str(data.avatar_url) if data.avatar_url else None,
        email_verified=False,  # será True al confirmar email
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def get_by_oauth(db: Session, provider: str, sub: str) -> User | None:
    return db.query(User).filter(User.oauth_provider == provider, User.oauth_sub == sub).first()

def upsert_oauth_user(db: Session, data: UserCreateOAuth) -> User:
    user = get_by_oauth(db, data.oauth_provider, data.oauth_sub)
    if user:
        # update básico
        if data.full_name and user.full_name != data.full_name:
            user.full_name = data.full_name
        if data.oauth_picture:
            user.oauth_picture = str(data.oauth_picture)
        if not user.email_verified and data.email_verified_from_provider:
            user.email_verified = True
    else:
        # ¿Existe por email? Vincular
        user = get_by_email(db, data.email)
        if user:
            user.oauth_provider = data.oauth_provider
            user.oauth_sub = data.oauth_sub
            if data.oauth_picture:
                user.oauth_picture = str(data.oauth_picture)
            if not user.email_verified and data.email_verified_from_provider:
                user.email_verified = True
        else:
            user = User(
                email=data.email,
                full_name=data.full_name,
                oauth_provider=data.oauth_provider,
                oauth_sub=data.oauth_sub,
                oauth_picture=str(data.oauth_picture) if data.oauth_picture else None,
                email_verified=bool(data.email_verified_from_provider),
                # sin password local
            )
            db.add(user)
    db.commit()
    db.refresh(user)
    return user

def mark_email_verified(db: Session, user: User) -> User:
    user.email_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user(db: Session, user: User, changes: UserUpdate) -> User:
    data = changes.model_dump(exclude_unset=True)
    if "avatar_url" in data and data["avatar_url"] is not None:
        data["avatar_url"] = str(data["avatar_url"])
    for field, value in data.items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
