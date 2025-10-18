import uuid
import pytest
from httpx import AsyncClient


async def _crear_producto_variantes(client: AsyncClient, admin_token: str):
    categoria = await client.post(
        "/api/v1/categories",
        json={"name": f"CartCat-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert categoria.status_code == 201, categoria.text
    cat = categoria.json()

    brand_resp = await client.post(
        "/api/v1/brands",
        json={"name": f"CartBrand-{uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert brand_resp.status_code == 201, brand_resp.text
    brand = brand_resp.json()

    prod_resp = await client.post(
        "/api/v1/products",
        json={
            "title": "Producto Cart",
            "price": 1200.0,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert prod_resp.status_code == 201, prod_resp.text
    product = prod_resp.json()

    variant_resp = await client.post(
        f"/api/v1/products/{product['id']}/variants",
        json={
            "sku": f"CART-{uuid.uuid4()}",
            "size_label": "U",
            "color_name": "Rojo",
            "stock_on_hand": 5,
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert variant_resp.status_code == 201, variant_resp.text
    variant = variant_resp.json()

    return product, variant


@pytest.mark.asyncio
async def test_cart_flow_authenticated(client: AsyncClient, admin_token: str):
    _, variant = await _crear_producto_variantes(client, admin_token)

    # Crear carrito (primer POST => 201)
    create_resp = await client.post(
        "/api/v1/cart",
        json={"currency": "ARS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_resp.status_code == 201, create_resp.text
    cart = create_resp.json()
    assert cart["items"] == []

    # Volver a crear debe devolver el mismo (200)
    create_again = await client.post(
        "/api/v1/cart",
        json={"currency": "ARS"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_again.status_code == 200

    # Agregar item
    add_resp = await client.post(
        "/api/v1/cart/items",
        json={"variant_id": variant["id"], "quantity": 2},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert add_resp.status_code == 201, add_resp.text
    cart = add_resp.json()
    assert len(cart["items"]) == 1
    item = cart["items"][0]
    assert item["quantity"] == 2
    assert cart["total_amount"] == 2400.0

    # Actualizar cantidad
    update_resp = await client.put(
        f"/api/v1/cart/items/{item['id']}",
        json={"quantity": 4},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert update_resp.status_code == 200, update_resp.text
    cart = update_resp.json()
    assert cart["items"][0]["quantity"] == 4
    assert cart["total_amount"] == 4800.0

    # Eliminar
    delete_resp = await client.delete(
        f"/api/v1/cart/items/{item['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert delete_resp.status_code == 200, delete_resp.text
    cart = delete_resp.json()
    assert cart["items"] == []
    assert cart["total_amount"] == 0.0


@pytest.mark.asyncio
async def test_cart_flow_guest(client: AsyncClient, admin_token: str):
    _, variant = await _crear_producto_variantes(client, admin_token)
    guest_token = f"guest-{uuid.uuid4()}"

    create_resp = await client.post(
        "/api/v1/cart",
        json={"guest_token": guest_token, "currency": "ARS"},
    )
    assert create_resp.status_code == 201, create_resp.text
    cart = create_resp.json()
    assert cart["guest_token"] == guest_token

    add_resp = await client.post(
        "/api/v1/cart/items",
        params={"guest_token": guest_token},
        json={"variant_id": variant["id"], "quantity": 1},
    )
    assert add_resp.status_code == 201, add_resp.text
    cart = add_resp.json()
    assert len(cart["items"]) == 1

    get_resp = await client.get(
        "/api/v1/cart",
        params={"guest_token": guest_token},
    )
    assert get_resp.status_code == 200
    fetched = get_resp.json()
    assert fetched["total_amount"] == 1200.0
