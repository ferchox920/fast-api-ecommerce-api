import uuid
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_product_question_flow(client: AsyncClient, admin_token: str, user_token: str):
    # crear producto
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": f"PQ-Cat-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": f"PQ-Brand-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201
    brand = r_brand.json()

    r_prod = await client.post(
        "/api/v1/products",
        json={
            "title": "Producto QA",
            "price": 500.0,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_prod.status_code == 201
    product = r_prod.json()

    # usuario formula pregunta
    question_resp = await client.post(
        f"/api/v1/products/{product['id']}/questions",
        json={"content": "Tiene garantía?"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert question_resp.status_code == 201, question_resp.text
    question = question_resp.json()
    assert question["status"] == "pending"

    # consulta publica
    list_resp = await client.get(f"/api/v1/products/{product['id']}/questions")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # admin responde
    answer_resp = await client.post(
        f"/api/v1/products/questions/{question['id']}/answer",
        json={"content": "Sí, 6 meses."},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert answer_resp.status_code == 200
    answered = answer_resp.json()
    assert answered["status"] == "answered"
    assert len(answered["answers"]) == 1

    # ocultar pregunta
    hide_resp = await client.patch(
        f"/api/v1/products/questions/{question['id']}/visibility",
        json={"is_visible": False},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert hide_resp.status_code == 200
    hidden = hide_resp.json()
    assert hidden["is_visible"] is False

    # bloquear pregunta
    block_resp = await client.patch(
        f"/api/v1/products/questions/{question['id']}/block",
        json={"is_blocked": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert block_resp.status_code == 200
    blocked = block_resp.json()
    assert blocked["is_blocked"] is True

    # listado publico ahora sin preguntas
    list_public = await client.get(f"/api/v1/products/{product['id']}/questions")
    assert list_public.status_code == 200
    assert list_public.json() == []

    # listado admin con include_hidden
    list_admin = await client.get(
        f"/api/v1/products/{product['id']}/questions",
        params={"include_hidden": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert list_admin.status_code == 200
    assert len(list_admin.json()) == 1


@pytest.mark.asyncio
async def test_notifications_flow(client: AsyncClient, admin_token: str, user_token: str):
    # crear producto para la orden
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
            "price": 800.0,
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
            "size_label": "U",
            "color_name": "Negro",
            "stock_on_hand": 5,
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    variant = r_variant.json()

    # user crea carrito y genera orden
    await client.post(
        "/api/v1/cart",
        json={"currency": "ARS"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant["id"], "quantity": 1},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_resp = await client.post(
        "/api/v1/orders/from-cart",
        json={},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert order_resp.status_code == 201
    order = order_resp.json()

    # admin marca pago y fulfill
    pay_resp = await client.post(
        f"/api/v1/orders/{order['id']}/pay",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert pay_resp.status_code == 200

    fulfill_resp = await client.post(
        f"/api/v1/orders/{order['id']}/fulfill",
        json={"carrier": "FastShip"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert fulfill_resp.status_code == 200

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
