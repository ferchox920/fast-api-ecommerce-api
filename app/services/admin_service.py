from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.user import User
from app.schemas.user import UserCreate
from app.services.user_service import create_user, get_by_email

def list_users(db: Session, skip: int = 0, limit: int = 50) -> Sequence[User]:
    stmt = (
        select(User)
        .order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()

def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id).first()

def create_user_as_admin(db: Session, payload: UserCreate, make_superuser: bool = False) -> User:
    if get_by_email(db, payload.email):
        raise ValueError("Email already registered")
    user = create_user(db, payload)
    if make_superuser:
        user.is_superuser = True
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

def set_admin_role(db: Session, user_id: str, make_admin: bool) -> User | None:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_superuser = bool(make_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def set_active(db: Session, user_id: str, active: bool) -> User | None:
    user = get_user_by_id(db, user_id)
    if not user:
        return None
    user.is_active = bool(active)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
