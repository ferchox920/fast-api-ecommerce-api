# tests/test_security_granular.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_manager_can_read_but_not_write(client: AsyncClient, manager_token: str, admin_token: str):
    # 1. Manager intenta LEER recursos protegidos (debería funcionar con 'purchases:read')
    resp_get_suppliers = await client.get(
        "/api/v1/purchases/suppliers",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp_get_suppliers.status_code == 200, resp_get_suppliers.text

    # 2. Manager intenta CREAR una categoría (no tiene 'products:write', debería fallar)
    resp_post_category = await client.post(
        "/api/v1/categories",
        json={"name": "Manager Category"},
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp_post_category.status_code == 403 # Esperamos Forbidden

    # 3. Admin CREA una categoría y marca para el siguiente paso
    rc = await client.post("/api/v1/categories", json={"name": "Admin Cat"},
                           headers={"Authorization": f"Bearer {admin_token}"})
    rb = await client.post("/api/v1/brands", json={"name": "Admin Brand"},
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert rc.status_code == 201 and rb.status_code == 201
    
    # 4. Manager intenta CREAR un producto (no tiene 'products:write', debería fallar)
    resp_post_prod = await client.post(
        "/api/v1/products",
        json={
            "title": "Manager Product", "price": 100, "currency": "USD",
            "category_id": rc.json()["id"], "brand_id": rb.json()["id"],
        },
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert resp_post_prod.status_code == 403 # Esperamos Forbidden