import uuid
import pytest
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.product import Category, Brand, Product, ProductVariant
from app.services import inventory_service
from fastapi import HTTPException
from app.models.supplier import Supplier


# ---------- helpers ----------

def _mk_variant(
    db: Session,
    *,
    on_hand=0,
    reserved=0,
    reorder_point=0,
    reorder_qty=0,
    primary_supplier_id=None,
) -> ProductVariant:
    cat = Category(name=f"Cat-{uuid.uuid4()}", slug=f"cat-{uuid.uuid4()}")
    brand = Brand(name=f"Brand-{uuid.uuid4()}", slug=f"brand-{uuid.uuid4()}")
    db.add_all([cat, brand])
    db.flush()

    p = Product(
        title=f"Prod-{uuid.uuid4()}",
        slug=f"prod-{uuid.uuid4()}",
        price=100,
        currency="ARS",
        category_id=cat.id,
        brand_id=brand.id,
        active=True,
    )
    db.add(p)
    db.flush()

    v = ProductVariant(
        product_id=p.id,
        sku=f"SKU-{uuid.uuid4()}",
        size_label="M",
        color_name="Black",
        stock_on_hand=on_hand,
        stock_reserved=reserved,
        reorder_point=reorder_point,
        reorder_qty=reorder_qty,
        primary_supplier_id=primary_supplier_id,
        active=True,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


# ---------- tests ----------

def test_receive_and_list_movements():
    db = SessionLocal()
    try:
        v = _mk_variant(db, on_hand=0)
        # receive + log
        inventory_service.receive_stock(db, v, 5, reason="ingreso OC")
        db.refresh(v)
        assert v.stock_on_hand == 5

        rows = inventory_service.list_movements(db, v, limit=10, offset=0)
        assert len(rows) >= 1
        last = rows[0]
        assert last["type"] == "receive"
        assert last["quantity"] == 5
        assert last["reason"] == "ingreso OC"
    finally:
        db.close()


def test_adjust_positive_and_negative_guards():
    db = SessionLocal()
    try:
        v = _mk_variant(db, on_hand=10)
        # ajuste positivo
        inventory_service.adjust_stock(db, v, +3, reason="ajuste +")
        db.refresh(v)
        assert v.stock_on_hand == 13

        # ajuste negativo válido
        inventory_service.adjust_stock(db, v, -3, reason="ajuste -")
        db.refresh(v)
        assert v.stock_on_hand == 10

        # ajuste que dejaría negativo -> 400
        with pytest.raises(HTTPException) as exc:
            inventory_service.adjust_stock(db, v, -11, reason="negativo")
        assert exc.value.status_code == 400
        assert "No puede quedar negativo" in exc.value.detail
    finally:
        db.close()


def test_reserve_and_release_validation():
    db = SessionLocal()
    try:
        v = _mk_variant(db, on_hand=5, reserved=0)

        # reservar más que on_hand -> 400
        with pytest.raises(HTTPException):
            inventory_service.reserve_stock(db, v, 6, reason="over")
        db.refresh(v)
        assert v.stock_reserved == 0

        # reservar 3
        inventory_service.reserve_stock(db, v, 3, reason="pedido")
        db.refresh(v)
        assert v.stock_reserved == 3
        assert v.stock_on_hand == 5  # no cambia on_hand al reservar

        # release más de lo reservado -> 400
        with pytest.raises(HTTPException):
            inventory_service.release_stock(db, v, 4, reason="over-release")

        # release 2
        inventory_service.release_stock(db, v, 2, reason="liberar")
        db.refresh(v)
        assert v.stock_reserved == 1
        assert v.stock_on_hand == 5
    finally:
        db.close()


def test_commit_sale_from_reserved_and_onhand():
    db = SessionLocal()
    try:
        v = _mk_variant(db, on_hand=10, reserved=3)

        # vender 2 -> consume reserved primero
        inventory_service.commit_sale(db, v, 2, reason="venta-1")
        db.refresh(v)
        assert v.stock_reserved == 1
        assert v.stock_on_hand == 8  # 10 - 2

        # vender 2 -> 1 de reservado + 1 de on_hand
        inventory_service.commit_sale(db, v, 2, reason="venta-2")
        db.refresh(v)
        assert v.stock_reserved == 0
        assert v.stock_on_hand == 6  # 8 - 2

        # vender más que on_hand -> 400
        with pytest.raises(HTTPException):
            inventory_service.commit_sale(db, v, 999, reason="no-stock")
    finally:
        db.close()


def test_alerts_and_replenishment_suggestion_without_supplier():
    db = SessionLocal()
    try:
        # available = 2-1 = 1 ; reorder_point=3 => alerta
        v = _mk_variant(db, on_hand=2, reserved=1, reorder_point=3, reorder_qty=5)

        alerts = inventory_service.compute_stock_alerts(db, supplier_id=None)
        hit = next((a for a in alerts if a.variant_id == v.id), None)
        assert hit is not None
        assert hit.available == 1
        assert hit.reorder_point == 3
        assert hit.missing == 2

        sugg = inventory_service.compute_replenishment_suggestion(db, supplier_id=None)
        line = next((l for l in sugg.lines if l.variant_id == v.id), None)
        assert line is not None
        # regla: max(missing, reorder_qty) con mínimo 1
        assert line.suggested_qty == 5
        assert "available(1) <= reorder_point(3)" in line.reason
    finally:
        db.close()


def test_alerts_and_replenishment_filtered_by_supplier():
    db = SessionLocal()
    try:
        supplier_id = uuid.uuid4()

        # crear fila en suppliers para respetar el FK
        unique_name = f"Test Supplier {uuid.uuid4()}"  # evitar UniqueViolation en ix_suppliers_name
        db.add(Supplier(id=supplier_id, name=unique_name))
        db.commit()

        v1 = _mk_variant(
            db,
            on_hand=1,
            reserved=1,          # available=0
            reorder_point=2,
            reorder_qty=4,
            primary_supplier_id=supplier_id,  # ahora sí existe
        )
        # v2 sin supplier o distinto -> no debe aparecer en filtro
        v2 = _mk_variant(
            db,
            on_hand=0,
            reserved=0,
            reorder_point=1,
            reorder_qty=2,
            primary_supplier_id=None,
        )

        alerts = inventory_service.compute_stock_alerts(db, supplier_id=supplier_id)
        ids = {a.variant_id for a in alerts}
        assert v1.id in ids
        assert v2.id not in ids

        sugg = inventory_service.compute_replenishment_suggestion(db, supplier_id=supplier_id)
        assert sugg.supplier_id == supplier_id
        line_ids = {l.variant_id for l in sugg.lines}
        assert v1.id in line_ids
        assert v2.id not in line_ids
    finally:
        db.close()


def test_invalid_quantities_raise_400():
    db = SessionLocal()
    try:
        v = _mk_variant(db, on_hand=5)

        with pytest.raises(HTTPException):
            inventory_service.receive_stock(db, v, 0)

        with pytest.raises(HTTPException):
            inventory_service.reserve_stock(db, v, -1)

        with pytest.raises(HTTPException):
            inventory_service.release_stock(db, v, 0)

        with pytest.raises(HTTPException):
            inventory_service.commit_sale(db, v, 0)
    finally:
        db.close()
