import uuid
import pytest
from httpx import AsyncClient


async def _create_product_with_variant(client: AsyncClient, admin_token: str) -> tuple[str, str]:
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": f"Notif-Cat-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cat = r_cat.json()
    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": f"Notif-Brand-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    brand = r_brand.json()
    r_prod = await client.post(
        "/api/v1/products",
        json={
            "title": "Producto Notif",
            "price": 1200.0,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product = r_prod.json()
    r_variant = await client.post(
        f"/api/v1/products/{product['id']}/variants",
        json={
            "sku": f"NOTIF-{uuid.uuid4()}",
            "size_label": "S",
            "color_name": "Verde",
            "stock_on_hand": 5,
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant = r_variant.json()
    return product["id"], variant["id"]


@pytest.mark.asyncio
async def test_notifications_order_flow(client: AsyncClient, admin_token: str, user_token: str):
    product_id, variant_id = await _create_product_with_variant(client, admin_token)

    # user creates cart and adds item
    cart_resp = await client.post(
        "/api/v1/cart",
        json={"currency": "ARS"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert cart_resp.status_code in (200, 201)

    add_item = await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant_id, "quantity": 1},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert add_item.status_code in (200, 201)

    order_resp = await client.post(
        "/api/v1/orders/from-cart",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert order_resp.status_code == 201, order_resp.text
    order = order_resp.json()

    # admin marks paid to trigger notification
    pay_resp = await client.post(
        f"/api/v1/orders/{order['id']}/pay",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pay_resp.status_code == 200

    notif_resp = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert notif_resp.status_code == 200
    notifications = notif_resp.json()
    assert len(notifications) >= 2

    first_id = notifications[0]["id"]
    mark_resp = await client.patch(
        f"/api/v1/notifications/{first_id}",
        json={"is_read": True},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert mark_resp.status_code == 200
    assert mark_resp.json()["is_read"] is True
