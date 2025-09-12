# tests/test_products.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_product_minimal(client: AsyncClient, admin_token: str):
    # 1) Crear categoría y marca para asociar al producto
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": "Remeras"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201, r_cat.text
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": "Nordic Wear"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201, r_brand.text
    brand = r_brand.json()

    # 2) Crear producto mínimo
    payload = {
        "title": "Remera Básica Blanca",
        "price": 9999.90,
        "currency": "ARS",
        "category_id": cat["id"],
        "brand_id": brand["id"],
    }
    r = await client.post(
        "/api/v1/products",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()

    # Validaciones básicas
    assert data["title"] == "Remera Básica Blanca"
    assert data["slug"] == "remera-basica-blanca"
    assert data["price"] == 9999.90
    assert data["currency"] == "ARS"
    assert data["active"] is True
    # Relaciones
    assert data["category"] is not None
    assert data["category"]["id"] == cat["id"]
    assert data["brand"] is not None
    assert data["brand"]["id"] == brand["id"]


@pytest.mark.asyncio
async def test_create_product_duplicate_slug(client: AsyncClient, admin_token: str):
    # Asegurar existan relaciones
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": "Pantalones"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201, r_cat.text
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": "Acme Denim"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201, r_brand.text
    brand = r_brand.json()

    base = {
        "title": "Jean Regular Fit",
        "price": 19999.00,
        "currency": "ARS",
        "category_id": cat["id"],
        "brand_id": brand["id"],
    }
    r1 = await client.post("/api/v1/products", json=base, headers={"Authorization": f"Bearer {admin_token}"})
    assert r1.status_code == 201, r1.text

    # mismo título => mismo slug => debe fallar (slug único)
    r2 = await client.post("/api/v1/products", json=base, headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 400
    assert "already exists" in r2.text.lower() or "unique" in r2.text.lower()


@pytest.mark.asyncio
async def test_public_list_products(client: AsyncClient, admin_token: str):
    # asegurar al menos uno
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": "Camperas"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201, r_cat.text
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": "WindBreaker"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201, r_brand.text
    brand = r_brand.json()

    await client.post(
        "/api/v1/products",
        json={
            "title": "Campera Rompevientos",
            "price": 24999.00,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # listado público paginado
    resp = await client.get("/api/v1/products")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert body["total"] >= 1
    # item shape mínimo
    item0 = body["items"][0]
    for key in ("id", "title", "slug", "price", "currency", "active"):
        assert key in item0
