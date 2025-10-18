from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Security, status, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import get_current_user
from app.core.notification_manager import manager as ws_manager
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationUpdate
from app.services import notification_service


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:me"]),
):
    notifications = notification_service.list_notifications(db, current_user, limit=limit, offset=offset)
    return notifications


@router.patch("/{notification_id}", response_model=NotificationRead)
def mark_notification(
    notification_id: str,
    payload: NotificationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["users:me"]),
):
    return notification_service.mark_read(db, notification_id, current_user, payload)


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: Optional[str] = None, db: Session = Depends(get_db)):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        token_data = deps.decode_token_no_db(token)
    except Exception:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if not token_data.sub:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = db.query(User).filter(User.id == token_data.sub).first()
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(user.id, websocket)
