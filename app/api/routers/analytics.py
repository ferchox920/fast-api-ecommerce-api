from fastapi import APIRouter, Depends, Security
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services import analytics_service

router = APIRouter(prefix="/admin/analytics", tags=["analytics"])


@router.get("/overview")
def overview(db: Session = Depends(get_db), current_user: User = Security(get_current_user, scopes=["admin"])):
    return analytics_service.overview(db)
