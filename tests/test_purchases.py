# tests/test_purchases.py
import pytest
from httpx import AsyncClient

# -------- helpers --------
async def _crear_base_minima(client: AsyncClient, admin_token: str):
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": "ComprasCat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201, r_cat.text
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": "ComprasBrand"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_brand.status_code == 201, r_brand.text
    brand = r_brand.json()

    r_prod = await client.post(
        "/api/v1/products",
        json={
            "title": "Producto Compras",
            "price": 1000.0,
            "currency": "ARS",
            "category_id": cat["id"],
            "brand_id": brand["id"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_prod.status_code == 201, r_prod.text
    prod = r_prod.json()

    rv = await client.post(
        f"/api/v1/products/{prod['id']}/variants",
        json={
            "sku": "PO-TEST-001",
            "size_label": "U",
            "color_name": "Negro",
            "color_hex": "#000000",
            "stock_on_hand": 0,
            "stock_reserved": 0,
            "active": True,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rv.status_code == 201, rv.text
    variant = rv.json()
    return cat, brand, prod, variant


# -------- tests --------

@pytest.mark.asyncio
async def test_supplier_create_and_list(client: AsyncClient, admin_token: str):
    # crear supplier
    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={
            "name": "Proveedor Uno",
            # ajusta si tu schema requiere campos extra:
            # "email": "compras@proveedoruno.com",
            # "phone": "+54 11 5555-5555",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201, rs.text
    sup = rs.json()
    assert sup["name"] == "Proveedor Uno"

    # listar suppliers
    rl = await client.get(
        "/api/v1/purchases/suppliers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rl.status_code == 200, rl.text
    data = rl.json()
    assert isinstance(data, list)
    assert any(s["id"] == sup["id"] for s in data)


@pytest.mark.asyncio
async def test_purchase_order_create(client: AsyncClient, admin_token: str):
    _, _, _, variant = await _crear_base_minima(client, admin_token)

    # crear supplier
    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={"name": "Proveedor PO"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201, rs.text
    supplier = rs.json()

    # crear PO con una línea
    rpo = await client.post(
        "/api/v1/purchases/orders",
        json={
            "supplier_id": supplier["id"],
            "currency": "ARS",
            "lines": [
                {
                    # Si tu API usa line_id en vez de variant_id, ajusta aquí:
                    "variant_id": variant["id"],
                    "quantity": 5,
                    "unit_cost": 800.0,
                }
            ],
            # agrega campos opcionales si tu schema los pide (expected_date, notes, etc.)
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rpo.status_code == 201, rpo.text
    po = rpo.json()
    assert po["supplier_id"] == supplier["id"]
    assert len(po.get("lines", [])) == 1
    line = po["lines"][0]
    assert line["quantity"] == 5


@pytest.mark.asyncio
async def test_purchase_order_receive_flow_updates_inventory(client: AsyncClient, admin_token: str):
    _, _, _, variant = await _crear_base_minima(client, admin_token)

    # Crear supplier
    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={"name": "Proveedor Recepciones"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201, rs.text
    supplier = rs.json()

    # Crear PO con qty 5
    rpo = await client.post(
        "/api/v1/purchases/orders",
        json={
            "supplier_id": supplier["id"],
            "currency": "ARS",
            "lines": [{"variant_id": variant["id"], "quantity": 5, "unit_cost": 750.0}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rpo.status_code == 201, rpo.text
    po = rpo.json()

    # --- usar line_id de la respuesta ---
    line_id = po["lines"][0]["id"]

    # recepción parcial: 3
    rr1 = await client.post(
        f"/api/v1/purchases/orders/{po['id']}/receive",
        json={"items": [{"line_id": line_id, "quantity": 3}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rr1.status_code == 200, rr1.text

    # verificar movimientos: debe existir receive de 3
    rm1 = await client.get(
        f"/api/v1/products/variants/{variant['id']}/stock/movements",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rm1.status_code == 200, rm1.text
    movs1 = rm1.json()
    assert any(m["type"] == "receive" and m["quantity"] == 3 for m in movs1)

    # recepción restante: 2
    rr2 = await client.post(
        f"/api/v1/purchases/orders/{po['id']}/receive",
        json={"items": [{"line_id": line_id, "quantity": 2}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rr2.status_code == 200, rr2.text

    # verificar que existan movimientos de 3 y 2
    rm2 = await client.get(
        f"/api/v1/products/variants/{variant['id']}/stock/movements",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rm2.status_code == 200, rm2.text
    movs2 = rm2.json()
    qtys = sorted([m["quantity"] for m in movs2 if m["type"] == "receive"])
    assert 2 in qtys and 3 in qtys
