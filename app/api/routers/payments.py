from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.operations import commit_async
from app.db.session_async import get_async_db
from app.models.user import User
from app.schemas.order import PaymentRead
from app.services import order_service, payment_service

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/orders/{order_id}", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment_for_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    order = await order_service.get_order(db, str(order_id))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    payment = await payment_service.create_payment_preference(db, order)
    await commit_async(db)
    await db.refresh(payment)
    return payment


@router.post("/mercado-pago/webhook", status_code=status.HTTP_200_OK)
async def mercado_pago_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    payload = await request.json()
    try:
        await payment_service.handle_mercado_pago_webhook(db, payload)
        await commit_async(db)
    except Exception:
        await db.rollback()
        raise
    return {"status": "ok"}
