# tests/test_brands.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_brand_as_admin(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/brands",
        json={"name": "Nordic Wear"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Nordic Wear"
    assert body["slug"] == "nordic-wear"
    assert body["active"] is True
