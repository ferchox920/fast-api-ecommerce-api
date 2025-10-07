# tests/test_purchases.py
import pytest
from httpx import AsyncClient
import uuid  # <--- AÑADIR IMPORT

# -------- helpers --------
async def _crear_base_minima(client: AsyncClient, admin_token: str):
    """
    Helper para crear una categoría, marca, producto y variante base para las pruebas.
    """
    cat_name = f"ComprasCat-{uuid.uuid4()}"
    r_cat = await client.post(
        "/api/v1/categories",
        json={"name": cat_name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_cat.status_code == 201, r_cat.text
    cat = r_cat.json()

    r_brand = await client.post(
        "/api/v1/brands",
        json={"name": f"ComprasBrand-{uuid.uuid4()}"},
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
            "sku": f"PO-TEST-{uuid.uuid4()}",  # SKU dinámico para evitar colisiones
            "size_label": "U",
            "color_name": "Negro",
            "stock_on_hand": 0,
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
    # crear supplier con nombre único
    supplier_name = f"Proveedor Uno {uuid.uuid4()}"
    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={"name": supplier_name},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201, rs.text
    sup = rs.json()
    assert sup["name"] == supplier_name

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

    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={"name": f"Proveedor PO {uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201, rs.text
    supplier = rs.json()

    rpo = await client.post(
        "/api/v1/purchases/orders",
        json={
            "supplier_id": supplier["id"],
            "lines": [{"variant_id": variant["id"], "quantity": 5, "unit_cost": 800.0}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rpo.status_code == 201, rpo.text
    po = rpo.json()
    assert po["supplier_id"] == supplier["id"]
    assert len(po.get("lines", [])) == 1
    assert po["lines"][0]["quantity"] == 5


@pytest.mark.asyncio
async def test_purchase_order_receive_flow_updates_inventory(client: AsyncClient, admin_token: str):
    # 👇 ahora también recibimos prod para usar su id en el GET
    _, _, prod, variant = await _crear_base_minima(client, admin_token)

    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={"name": f"Proveedor Recepciones {uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201, rs.text
    supplier = rs.json()

    rpo = await client.post(
        "/api/v1/purchases/orders",
        json={
            "supplier_id": supplier["id"],
            "lines": [{"variant_id": variant["id"], "quantity": 5, "unit_cost": 750.0}],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rpo.status_code == 201, rpo.text
    po = rpo.json()
    line_id = po["lines"][0]["id"]

    # Recepción parcial: 3
    rr1 = await client.post(
        f"/api/v1/purchases/orders/{po['id']}/receive",
        json={"items": [{"line_id": line_id, "quantity": 3}]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rr1.status_code == 200, rr1.text

    # Verificar stock — usar el product.id del helper (no 'product_id' dentro de variant)
    r_variants_get = await client.get(
        f"/api/v1/products/{prod['id']}/variants",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert r_variants_get.status_code == 200

    variant_after_receive = next((v for v in r_variants_get.json() if v['id'] == variant['id']), None)
    assert variant_after_receive is not None
    assert variant_after_receive['stock_on_hand'] == 3


# ===============================================================
# ===== NUEVA PRUEBA AÑADIDA ====================================
# ===============================================================
@pytest.mark.asyncio
async def test_create_po_from_suggestions(client: AsyncClient, admin_token: str):
    # 1. Crear un proveedor
    rs = await client.post(
        "/api/v1/purchases/suppliers",
        json={"name": f"Proveedor Sugerencias {uuid.uuid4()}"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rs.status_code == 201
    supplier = rs.json()

    # 2. Crear un producto y variante con necesidad de reposición
    _, _, _, variant = await _crear_base_minima(client, admin_token)

    # Actualizar la variante para que active una alerta
    r_update = await client.put(
        f"/api/v1/products/variants/{variant['id']}",
        json={
            "stock_on_hand": 1,
            "reorder_point": 5,
            "reorder_qty": 10,
            "primary_supplier_id": supplier["id"]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_update.status_code == 200

    # 3. Llamar al nuevo endpoint para generar la PO
    r_po_sugg = await client.post(
        "/api/v1/purchases/orders/from-suggestions",
        json={"supplier_id": supplier["id"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_po_sugg.status_code == 201, r_po_sugg.text
    po = r_po_sugg.json()

    # 4. Verificar que la PO se creó correctamente
    assert po["supplier_id"] == supplier["id"]
    assert po["status"] == "draft"
    assert len(po["lines"]) == 1

    line = po["lines"][0]
    assert line["variant_id"] == variant["id"]
    assert line["quantity"] == 10  # reorder_qty (10) > missing (4)
