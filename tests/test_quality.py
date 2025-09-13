# tests/test_quality.py
import pytest
from httpx import AsyncClient

async def _base(client, admin_token):
    rc = await client.post("/api/v1/categories", json={"name":"QualCat"}, headers={"Authorization": f"Bearer {admin_token}"})
    rb = await client.post("/api/v1/brands", json={"name":"QualBrand"}, headers={"Authorization": f"Bearer {admin_token}"})
    rp = await client.post("/api/v1/products", json={
        "title":"ProdQ",
        "price":1000.0, "currency":"ARS",
        "category_id": rc.json()["id"], "brand_id": rb.json()["id"],
        "description": "Corto",  # < 50
    }, headers={"Authorization": f"Bearer {admin_token}"})
    return rp.json()

@pytest.mark.asyncio
async def test_quality_improves_with_images_and_desc(client: AsyncClient, admin_token: str):
    p = await _base(client, admin_token)
    q1 = await client.get(f"/api/v1/products/{p['id']}/quality", headers={"Authorization": f"Bearer {admin_token}"})
    s1 = q1.json()["score"]
    assert s1 < 100

    # Agrego imagen principal automática
    await client.post(f"/api/v1/products/{p['id']}/images", json={"url":"https://example.com/p.jpg"},
                      headers={"Authorization": f"Bearer {admin_token}"})

    # Agrego una variante activa
    await client.post(f"/api/v1/products/{p['id']}/variants", json={
        "sku":"Q-001","size_label":"U","color_name":"Negro","color_hex":"#000000",
        "stock_on_hand":1,"stock_reserved":0,"active":True
    }, headers={"Authorization": f"Bearer {admin_token}"})

    # Mejoro descripción
    await client.put(f"/api/v1/products/{p['id']}", json={"description":"Descripción suficientemente larga " * 3},
                     headers={"Authorization": f"Bearer {admin_token}"})

    q2 = await client.get(f"/api/v1/products/{p['id']}/quality", headers={"Authorization": f"Bearer {admin_token}"})
    s2 = q2.json()["score"]
    assert s2 > s1
