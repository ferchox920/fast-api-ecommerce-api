from __future__ import annotations

import httpx

from app.core.config import settings
from app.models.order import Order
from app.services.payment_providers import (
    PaymentProviderError,
    PaymentProviderConfigurationError,
)


API_BASE_URL = "https://api.mercadopago.com"


def _get_access_token() -> str:
    token = settings.MERCADO_PAGO_ACCESS_TOKEN
    if not token:
        raise PaymentProviderConfigurationError("Mercado Pago access token is not configured")
    return token


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_get_access_token()}",
        "Content-Type": "application/json",
    }


def create_checkout_preference(order: Order) -> dict:
    items = [
        {
            "id": str(line.variant_id),
            "title": f"SKU {line.variant_id}",
            "quantity": int(line.quantity),
            "currency_id": order.currency,
            "unit_price": float(line.unit_price),
        }
        for line in order.lines
    ]

    payload = {
        "external_reference": str(order.id),
        "items": items,
        "back_urls": {
            "success": settings.MERCADO_PAGO_SUCCESS_URL,
            "failure": settings.MERCADO_PAGO_FAILURE_URL,
            "pending": settings.MERCADO_PAGO_PENDING_URL,
        },
        "auto_return": "approved",
        "metadata": {
            "order_id": str(order.id),
            "project": settings.PROJECT_NAME,
        },
    }

    if settings.MERCADO_PAGO_NOTIFICATION_URL:
        payload["notification_url"] = settings.MERCADO_PAGO_NOTIFICATION_URL

    try:
        response = httpx.post(
            f"{API_BASE_URL}/checkout/preferences",
            json=payload,
            headers=_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PaymentProviderError(f"Mercado Pago error: {exc.response.text}") from exc
    except httpx.HTTPError as exc:
        raise PaymentProviderError(f"Mercado Pago connection error: {exc}") from exc

    return response.json()


def get_payment(payment_id: str) -> dict:
    try:
        response = httpx.get(
            f"{API_BASE_URL}/v1/payments/{payment_id}",
            headers=_headers(),
            timeout=15.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise PaymentProviderError(f"Mercado Pago error: {exc.response.text}") from exc
    except httpx.HTTPError as exc:
        raise PaymentProviderError(f"Mercado Pago connection error: {exc}") from exc

    return response.json()
