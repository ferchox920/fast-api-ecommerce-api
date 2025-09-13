import pytest
from httpx import AsyncClient

async def _producto_minimo(client, admin_token):
    rc = await client.post("/api/v1/categories", json={"name": "InvCat"}, headers={"Authorization": f"Bearer {admin_token}"})
    rb = await client.post("/api/v1/brands", json={"name": "InvBrand"}, headers={"Authorization": f"Bearer {admin_token}"})
    rp = await client.post("/api/v1/products", json={
        "title": "InvProd", "price": 1000.0, "currency": "ARS", "category_id": rc.json()["id"], "brand_id": rb.json()["id"],
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return rp.json()

@pytest.mark.asyncio
async def test_receive_reserve_release_sale_flow(client: AsyncClient, admin_token: str):
    prod = await _producto_minimo(client, admin_token)
    # crear variante
    rv = await client.post(f"/api/v1/products/{prod['id']}/variants", json={
        "sku": "INV-001", "size_label": "U", "color_name": "Negro", "color_hex": "#000000",
        "stock_on_hand": 0, "stock_reserved": 0, "active": True
    }, headers={"Authorization": f"Bearer {admin_token}"})
    assert rv.status_code == 201
    var = rv.json()

    # receive 10
    r1 = await client.post(f"/api/v1/products/variants/{var['id']}/stock/receive",
        json={"type":"receive", "quantity":10}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r1.status_code == 200 and r1.json()["stock_on_hand"] == 10

    # reserve 6
    r2 = await client.post(f"/api/v1/products/variants/{var['id']}/stock/reserve",
        json={"type":"reserve", "quantity":6}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 200 and r2.json()["stock_reserved"] == 6

    # release 2
    r3 = await client.post(f"/api/v1/products/variants/{var['id']}/stock/release",
        json={"type":"release", "quantity":2}, headers={"Authorization": f"Bearer {admin_token}"})
    v3 = r3.json()
    assert r3.status_code == 200 and v3["stock_reserved"] == 4 and v3["stock_on_hand"] == 10

    # sale 3 (de reservado)
    r4 = await client.post(f"/api/v1/products/variants/{var['id']}/stock/sale",
        json={"type":"sale", "quantity":3}, headers={"Authorization": f"Bearer {admin_token}"})
    v4 = r4.json()
    assert v4["stock_reserved"] == 1 and v4["stock_on_hand"] == 7

    # movimientos
    rm = await client.get(f"/api/v1/products/variants/{var['id']}/stock/movements",
        headers={"Authorization": f"Bearer {admin_token}"})
    assert rm.status_code == 200
    assert len(rm.json()) >= 4

@pytest.mark.asyncio
async def test_reserve_more_than_available_fails(client: AsyncClient, admin_token: str):
    prod = await _producto_minimo(client, admin_token)
    rv = await client.post(f"/api/v1/products/{prod['id']}/variants", json={
        "sku": "INV-002", "size_label": "U", "color_name": "Azul", "color_hex": "#0000FF",
        "stock_on_hand": 5, "stock_reserved": 0, "active": True
    }, headers={"Authorization": f"Bearer {admin_token}"})
    var = rv.json()
    r = await client.post(f"/api/v1/products/variants/{var['id']}/stock/reserve",
        json={"type":"reserve", "quantity":6}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 400
