from typing import Optional

from fastapi import APIRouter, Depends, Security, HTTPException, status, Request
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.order import PaymentRead
from app.services import order_service, payment_service


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/orders/{order_id}", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
def create_payment_for_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["orders:write"]),
):
    order = order_service.get_order(db, str(order_id))
    if not order:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")

    payment = payment_service.create_payment_preference(db, order)
    return payment


@router.post("/mercado-pago/webhook", status_code=status.HTTP_200_OK)
async def mercado_pago_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    payload = await request.json()
    payment_service.handle_mercado_pago_webhook(db, payload)
    return {"status": "ok"}
