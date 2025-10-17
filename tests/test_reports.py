# tests/test_reports.py
import pytest
from httpx import AsyncClient
import uuid

# --- Helper para crear un escenario completo de prueba ---
async def _setup_report_scenario(client: AsyncClient, admin_token: str):
    """
    Crea un ecosistema completo para probar los reportes:
    1. Supplier, Category, Brand, Product, Variant.
    2. Una Purchase Order con un costo específico.
    3. Recepción de la PO para generar stock y un costo histórico.
    4. Una venta para generar movimientos de tipo 'sale'.
    Devuelve los IDs y datos clave para las aserciones.
    """
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Crear entidades base
    r_cat = await client.post("/api/v1/categories", json={"name": f"Cat-Report-{uuid.uuid4()}"}, headers=headers)
    r_brand = await client.post("/api/v1/brands", json={"name": f"Brand-Report-{uuid.uuid4()}"}, headers=headers)
    r_supp = await client.post("/api/v1/purchases/suppliers", json={"name": f"Supp-Report-{uuid.uuid4()}"}, headers=headers)
    
    assert all(r.status_code == 201 for r in [r_cat, r_brand, r_supp])
    cat, brand, supplier = r_cat.json(), r_brand.json(), r_supp.json()

    r_prod = await client.post("/api/v1/products", json={
        "title": "Producto para Reportes", "price": 1500.0, "currency": "ARS",
        "category_id": cat["id"], "brand_id": brand["id"],
    }, headers=headers)
    assert r_prod.status_code == 201
    prod = r_prod.json()

    r_var = await client.post(f"/api/v1/products/{prod['id']}/variants", json={
        "sku": f"REP-SKU-{uuid.uuid4()}", "size_label": "M", "color_name": "Azul",
        "stock_on_hand": 0, "active": True,
    }, headers=headers)
    assert r_var.status_code == 201
    variant = r_var.json()

    # 2. Crear y recibir una Purchase Order
    unit_cost = 500.0
    qty_ordered = 10
    r_po = await client.post("/api/v1/purchases/orders", json={
        "supplier_id": supplier["id"],
        "lines": [{"variant_id": variant["id"], "quantity": qty_ordered, "unit_cost": unit_cost}],
    }, headers=headers)
    assert r_po.status_code == 201
    po = r_po.json()

    # Colocar y recibir la PO para que el costo cuente
    await client.post(f"/api/v1/purchases/orders/{po['id']}/place", headers=headers)
    r_rcv = await client.post(f"/api/v1/purchases/orders/{po['id']}/receive", json={
        "items": [{"line_id": po["lines"][0]["id"], "quantity": qty_ordered}]
    }, headers=headers)
    assert r_rcv.status_code == 200

    # 3. Generar una venta
    # Primero, reservamos el stock para la venta
    await client.post(f"/api/v1/products/variants/{variant['id']}/stock/reserve", json={
        "type": "reserve", "quantity": 3, "reason": "Test Reserve for Sale"
    }, headers=headers)
    
    qty_sold = 3
    r_sale = await client.post(f"/api/v1/products/variants/{variant['id']}/stock/sale", json={
        "type": "sale", "quantity": qty_sold, "reason": "Test Sale"
    }, headers=headers)
    assert r_sale.status_code == 200
    
    final_stock = qty_ordered - qty_sold
    
    return {
        "variant": variant,
        "unit_cost": unit_cost,
        "qty_ordered": qty_ordered,
        "qty_sold": qty_sold,
        "final_stock": final_stock
    }


# --- Tests para los nuevos endpoints ---

@pytest.mark.asyncio
async def test_get_inventory_value_report(client: AsyncClient, admin_token: str):
    scenario = await _setup_report_scenario(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Llamar al endpoint
    r = await client.get("/api/v1/reports/inventory/value", headers=headers)
    assert r.status_code == 200, r.text
    report = r.json()

    # Validar estructura y valores
    assert "total_estimated_value" in report
    assert report["total_units"] > 0
    
    item = next((i for i in report["items"] if i["variant_id"] == scenario["variant"]["id"]), None)
    assert item is not None
    
    assert item["stock_on_hand"] == scenario["final_stock"]
    assert item["last_unit_cost"] == scenario["unit_cost"]
    assert item["estimated_value"] == pytest.approx(scenario["final_stock"] * scenario["unit_cost"])
    assert report["total_estimated_value"] >= item["estimated_value"]


@pytest.mark.asyncio
async def test_get_cost_analysis_report(client: AsyncClient, admin_token: str):
    scenario = await _setup_report_scenario(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Llamar al endpoint
    r = await client.get("/api/v1/reports/purchases/cost-analysis", headers=headers)
    assert r.status_code == 200, r.text
    report = r.json()

    # Validar estructura y valores
    assert "total_purchase_cost" in report
    item = next((i for i in report["items_by_product"] if i["variant_id"] == scenario["variant"]["id"]), None)
    assert item is not None

    assert item["units_purchased"] == scenario["qty_ordered"]
    assert item["total_cost"] == pytest.approx(scenario["qty_ordered"] * scenario["unit_cost"])
    assert item["average_cost"] == pytest.approx(scenario["unit_cost"])


@pytest.mark.asyncio
async def test_get_inventory_rotation_report(client: AsyncClient, admin_token: str):
    scenario = await _setup_report_scenario(client, admin_token)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Llamar al endpoint
    r = await client.get("/api/v1/reports/inventory/rotation", headers=headers)
    assert r.status_code == 200, r.text
    report = r.json()

    # Validar estructura y valores
    assert "items" in report
    item = next((i for i in report["items"] if i["variant_id"] == scenario["variant"]["id"]), None)
    assert item is not None

    assert item["units_sold"] == scenario["qty_sold"]
    assert item["current_stock"] == scenario["final_stock"]
    if scenario["final_stock"] > 0:
        expected_ratio = scenario["qty_sold"] / scenario["final_stock"]
        assert item["turnover_ratio"] == pytest.approx(expected_ratio)
    else:
        assert item["turnover_ratio"] == 0 # Or whatever the expected behavior is for zero stock
