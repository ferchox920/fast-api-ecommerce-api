# tests/test_auth.py
import pytest

LOGIN_URL = "/api/v1/auth/login"
PROTECTED_URL = "/api/v1/categories"

@pytest.mark.asyncio
async def test_login_success(client, admin_user):
    resp = await client.post(
        LOGIN_URL,
        data={"username": admin_user.email, "password": "Admin1234"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # tokens típicos
    assert "access_token" in body
    assert body.get("token_type", "").lower() in ("bearer", "jwt", "access")

@pytest.mark.asyncio
async def test_login_wrong_password(client, admin_user):
    resp = await client.post(
        LOGIN_URL,
        data={"username": admin_user.email, "password": "wrong-pass"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # algunos auth devuelven 400, otros 401 -> aceptamos ambos
    assert resp.status_code in (400, 401), resp.text
    msg = resp.text.lower()
    assert ("invalid" in msg) or ("incorrect" in msg) or ("unauthorized" in msg)

@pytest.mark.asyncio
async def test_protected_requires_auth(client):
    # crear categoría sin token => 401
    resp = await client.post(PROTECTED_URL, json={"name": "Protegida"})
    assert resp.status_code in (401, 403), resp.text

@pytest.mark.asyncio
async def test_protected_with_token(client, admin_token):
    # crear categoría con token => 201
    resp = await client.post(
        PROTECTED_URL,
        json={"name": "Autorizada"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Autorizada"
    assert "slug" in data
    assert data.get("active") is True
