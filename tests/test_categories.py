# tests/test_categories.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_category_as_admin(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/api/v1/categories",
        json={"name": "Remeras"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Remeras"
    assert data["slug"] == "remeras"
    assert data["active"] is True

@pytest.mark.asyncio
async def test_create_category_duplicate_slug(client: AsyncClient, admin_token: str):
    # mismo nombre -> mismo slug -> debe fallar en create (según política que dejamos)
    await client.post(
        "/api/v1/categories",
        json={"name": "Camperas"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    r2 = await client.post(
        "/api/v1/categories",
        json={"name": "Camperas"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code in (400, 409)
