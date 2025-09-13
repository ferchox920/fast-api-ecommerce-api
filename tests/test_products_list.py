# tests/test_products_list.py
import pytest
from httpx import AsyncClient

async def _crear_base_minima(client: AsyncClient, token: str):
    r_cat = await client.post("/api/v1/categories", json={"name": "Ropa"},
                              headers={"Authorization": f"Bearer {token}"})
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post("/api/v1/brands", json={"name": "Acme"},
                                headers={"Authorization": f"Bearer {token}"})
    assert r_brand.status_code == 201
    brand = r_brand.json()
    return cat, brand

async def _crear_producto(client: AsyncClient, token: str, title: str, price: float, cat_id: str, brand_id: str):
    payload = {
        "title": title,
        "price": price,
        "currency": "ARS",
        "category_id": cat_id,
        "brand_id": brand_id,
    }
    r = await client.post("/api/v1/products", json=payload,
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201, r.text
    return r.json()

@pytest.mark.asyncio
async def test_products_pagination_and_filters(client: AsyncClient, admin_token: str):
    cat, brand = await _crear_base_minima(client, admin_token)

    # Creamos 25 productos con distintos precios
    for i in range(25):
        await _crear_producto(
            client, admin_token,
            title=f"Remera {i}",
            price=1000 + i * 1000,  # 1000, 2000, ..., 26000
            cat_id=cat["id"], brand_id=brand["id"]
        )

    # Página 1 (limit=10)
    r1 = await client.get("/api/v1/products?limit=10&offset=0")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["total"] == 25
    assert d1["page"] == 1
    assert d1["pages"] == 3
    assert len(d1["items"]) == 10

    # Página 3 (offset=20)
    r3 = await client.get("/api/v1/products?limit=10&offset=20")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["page"] == 3
    assert len(d3["items"]) == 5  # 25 totales

    # Filtro por rango de precio (>= 10000 y <= 15000)
    r_price = await client.get("/api/v1/products?min_price=10000&max_price=15000")
    assert r_price.status_code == 200
    dp = r_price.json()
    assert dp["total"] > 0
    for it in dp["items"]:
        assert 10000 <= it["price"] <= 15000

    # Filtro de búsqueda
    r_search = await client.get("/api/v1/products?search=Remera 2")
    assert r_search.status_code == 200
    ds = r_search.json()
    assert ds["total"] >= 1
    assert any("Remera 2" in it["title"] for it in ds["items"])
