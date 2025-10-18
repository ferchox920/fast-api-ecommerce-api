import uuid
import pytest
from httpx import AsyncClient

from app.models.order import PaymentStatus


async def _create_order(client: AsyncClient, admin_token: str):
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": f"PaymentsCat-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": f"PaymentsBrand-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201
    brand = r_brand.json()

    r_prod = await client.post(
        "/api/v1/products",
        json={
            "title": "Producto Pagos",
            "price": 2000.0,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_prod.status_code == 201
    prod = r_prod.json()

    r_variant = await client.post(
        f"/api/v1/products/{prod['id']}/variants",
        json={
            "sku": f"PAY-TEST-{uuid.uuid4()}",
            "size_label": "M",
            "color_name": "Rojo",
            "stock_on_hand": 10,
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_variant.status_code == 201
    variant = r_variant.json()

    ro = await client.post(
        "/api/v1/orders",
        json={
            "currency": "ARS",
            "lines": [
                {"variant_id": variant["id"], "quantity": 1}
            ],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert ro.status_code == 201
    return ro.json()


@pytest.mark.asyncio
async def test_payment_preference_creation(client: AsyncClient, admin_token: str, monkeypatch):
    order = await _create_order(client, admin_token)

    fake_pref = {
        "id": "pref-123",
        "init_point": "https://mp.test/init",
        "sandbox_init_point": "https://mp.test/sandbox",
    }

    monkeypatch.setattr(
        "app.services.payment_providers.mercado_pago.create_checkout_preference",
        lambda order_obj: fake_pref,
    )

    resp = await client.post(
        f"/api/v1/payments/orders/{order['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    payment = resp.json()
    assert payment["provider"] == "mercado_pago"
    assert payment["init_point"] == fake_pref["init_point"]
    assert payment["status"] == "pending"

    # El endpoint de la orden debe reflejar el pago pendiente
    order_after = await client.get(
        f"/api/v1/orders/{order['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert order_after.status_code == 200
    data = order_after.json()
    assert data["payment_status"] == "pending"
    assert len(data["payments"]) == 1


@pytest.mark.asyncio
async def test_payment_webhook_updates_order(client: AsyncClient, admin_token: str, monkeypatch):
    order = await _create_order(client, admin_token)

    fake_pref = {
        "id": "pref-456",
        "init_point": "https://mp.test/init",
        "sandbox_init_point": "https://mp.test/sandbox",
    }

    monkeypatch.setattr(
        "app.services.payment_providers.mercado_pago.create_checkout_preference",
        lambda order_obj: fake_pref,
    )

    resp = await client.post(
        f"/api/v1/payments/orders/{order['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201

    monkeypatch.setattr(
        "app.services.payment_providers.mercado_pago.get_payment",
        lambda payment_id: {
            "id": payment_id,
            "status": "approved",
            "status_detail": "accredited",
        },
    )

    webhook_resp = await client.post(
        "/api/v1/payments/mercado-pago/webhook",
        json={"data": {"id": fake_pref["id"]}},
    )
    assert webhook_resp.status_code == 200

    order_after = await client.get(
        f"/api/v1/orders/{order['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert order_after.status_code == 200
    data = order_after.json()
    assert data["status"] == "paid"
    assert data["payment_status"] == "approved"
