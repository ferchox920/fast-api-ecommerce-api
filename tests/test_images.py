# tests/test_images.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_add_first_image_is_primary(client: AsyncClient, admin_token: str):
    # Crear categoría/marca mínimas
    r_cat = await client.post("/api/v1/categories", json={"name": "Accesorios"},
                              headers={"Authorization": f"Bearer {admin_token}"})
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post("/api/v1/brands", json={"name": "PixBrand"},
                                headers={"Authorization": f"Bearer {admin_token}"})
    assert r_brand.status_code == 201
    brand = r_brand.json()

    # Crear producto
    payload = {
        "title": "Gorra Negra",
        "price": 5000.0,
        "currency": "ARS",
        "category_id": cat["id"],
        "brand_id": brand["id"],
    }
    r_prod = await client.post("/api/v1/products", json=payload,
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_prod.status_code == 201, r_prod.text
    prod = r_prod.json()

    # Subir PRIMERA imagen sin is_primary => debe quedar principal
    img_payload = {"url": "https://example.com/gorra1.jpg", "alt_text": "Gorra vista 1"}
    r_img = await client.post(f"/api/v1/products/{prod['id']}/images",
                              json=img_payload,
                              headers={"Authorization": f"Bearer {admin_token}"})
    assert r_img.status_code == 201, r_img.text
    img1 = r_img.json()
    assert img1["is_primary"] is True

    # Subir SEGUNDA imagen por defecto => no principal
    r_img2 = await client.post(f"/api/v1/products/{prod['id']}/images",
                               json={"url": "https://example.com/gorra2.jpg"},
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_img2.status_code == 201
    img2 = r_img2.json()
    assert img2["is_primary"] is False


@pytest.mark.asyncio
async def test_add_image_with_is_primary_switches(client: AsyncClient, admin_token: str):
    # Base mínima
    r_cat = await client.post("/api/v1/categories", json={"name": "Remeras"},
                              headers={"Authorization": f"Bearer {admin_token}"})
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post("/api/v1/brands", json={"name": "SwitchPic"},
                                headers={"Authorization": f"Bearer {admin_token}"})
    assert r_brand.status_code == 201
    brand = r_brand.json()

    r_prod = await client.post("/api/v1/products",
                               json={
                                   "title": "Remera Blanca",
                                   "price": 9999.0,
                                   "currency": "ARS",
                                   "category_id": cat["id"],
                                   "brand_id": brand["id"],
                               },
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_prod.status_code == 201
    prod = r_prod.json()

    # Primera imagen (principal automática)
    r_img1 = await client.post(f"/api/v1/products/{prod['id']}/images",
                               json={"url": "https://example.com/remera1.jpg"},
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_img1.status_code == 201
    img1 = r_img1.json()
    assert img1["is_primary"] is True

    # Segunda imagen con is_primary=True => debería rotar principal
    r_img2 = await client.post(f"/api/v1/products/{prod['id']}/images",
                               json={"url": "https://example.com/remera2.jpg", "is_primary": True},
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_img2.status_code == 201
    img2 = r_img2.json()
    assert img2["is_primary"] is True

    # Confirmar en el GET público que la principal actual es img2
    r_get = await client.get(f"/api/v1/products/{prod['slug']}")
    assert r_get.status_code == 200
    p = r_get.json()
    primaries = [i for i in p["images"] if i["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == img2["id"]


@pytest.mark.asyncio
async def test_set_primary_image_endpoint(client: AsyncClient, admin_token: str):
    # Base mínima
    r_cat = await client.post("/api/v1/categories", json={"name": "Calzado"},
                              headers={"Authorization": f"Bearer {admin_token}"})
    assert r_cat.status_code == 201
    cat = r_cat.json()

    r_brand = await client.post("/api/v1/brands", json={"name": "FootPix"},
                                headers={"Authorization": f"Bearer {admin_token}"})
    assert r_brand.status_code == 201
    brand = r_brand.json()

    r_prod = await client.post("/api/v1/products",
                               json={
                                   "title": "Zapatilla Runner",
                                   "price": 29999.0,
                                   "currency": "ARS",
                                   "category_id": cat["id"],
                                   "brand_id": brand["id"],
                               },
                               headers={"Authorization": f"Bearer {admin_token}"})
    assert r_prod.status_code == 201
    prod = r_prod.json()

    # Dos imágenes
    r1 = await client.post(f"/api/v1/products/{prod['id']}/images",
                           json={"url": "https://example.com/zapa1.jpg"},
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert r1.status_code == 201
    img1 = r1.json()

    r2 = await client.post(f"/api/v1/products/{prod['id']}/images",
                           json={"url": "https://example.com/zapa2.jpg"},
                           headers={"Authorization": f"Bearer {admin_token}"})
    assert r2.status_code == 201
    img2 = r2.json()

    # Setear como principal la 2
    r_primary = await client.post(
        f"/api/v1/products/{prod['id']}/images/{img2['id']}/primary",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_primary.status_code == 200
    product_after = r_primary.json()
    primaries = [i for i in product_after["images"] if i["is_primary"]]
    assert len(primaries) == 1
    assert primaries[0]["id"] == img2["id"]
