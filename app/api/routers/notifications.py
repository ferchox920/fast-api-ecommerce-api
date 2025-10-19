from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.api.deps import get_current_user
from app.core.notification_manager import manager as ws_manager
from app.db.operations import run_sync
from app.db.session_async import get_async_db
from app.models.user import User
from app.schemas.notification import NotificationRead, NotificationUpdate
from app.services import notification_service
from app.services.exceptions import ServiceError


router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["users:me"]),
):
    return await run_sync(db, notification_service.list_notifications, current_user, limit, offset)


@router.patch("/{notification_id}", response_model=NotificationRead)
async def mark_notification(
    notification_id: str,
    payload: NotificationUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["users:me"]),
):
    try:
        notif = await run_sync(db, notification_service.mark_read, notification_id, current_user, payload)
        await db.commit()
    except ServiceError:
        await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
    await db.refresh(notif)
    return notif


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: Optional[str] = None, db: AsyncSession = Depends(get_async_db)):
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

    user = await db.get(User, token_data.sub)
    if not user or not user.is_active:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await ws_manager.connect(user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(user.id, websocket)
