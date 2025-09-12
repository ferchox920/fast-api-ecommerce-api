# app/api/routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.user import User as UserModel
from app.schemas.user import UserRead, UserCreate, UserUpdate
from app.services.user_service import create_user, get_by_email, update_user

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
def read_me(current_user: UserModel = Depends(get_current_active_user)):
    return current_user

@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(data: UserCreate, db: Session = Depends(get_db)):
    existing = get_by_email(db, data.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, data)
    # En registro local, se envía verificación por correo fuera de este endpoint (cliente pega /auth/verify/request)
    return user

@router.put("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_active_user),
):
    user = update_user(db, current_user, payload)
    return user
