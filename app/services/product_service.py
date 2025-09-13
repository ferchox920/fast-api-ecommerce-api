# app/services/product_service.py
from typing import Sequence, TYPE_CHECKING
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func, text, inspect
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
import re
import unicodedata
import uuid

from app.models.product import (
    Product, ProductVariant, ProductImage, Category, Brand
)
from app.schemas.product import (
    ProductCreate, ProductUpdate,
    ProductVariantCreate, ProductVariantUpdate,
    ProductImageCreate
)

if TYPE_CHECKING:
    # Solo para type hints, no ejecuta en runtime (evita ciclos)
    from app.models.inventory import InventoryMovement as _InventoryMovement


# ---------------- Utils: slug ----------------
def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text.lower()

def _slug_exists(db: Session, slug: str) -> bool:
    return db.query(Product).filter(Product.slug == slug).first() is not None

# ---------------- Utils: UUID ----------------
def _as_uuid(value: str | uuid.UUID | None, field: str) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid UUID for {field}")

# ---------- Lectura pública ----------
def list_products(
    db: Session,
    q: str | None = None,
    category_id: str | None = None,
    brand_id: str | None = None,
    color: str | None = None,
    size: str | None = None,
    gender: str | None = None,
    fit: str | None = None,
    season: str | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    skip: int = 0,
    limit: int = 20,
) -> Sequence[Product]:
    stmt = select(Product).where(Product.active == True)  # noqa: E712

    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Product.title.ilike(like), Product.description.ilike(like)))
    if category_id:
        stmt = stmt.where(Product.category_id == _as_uuid(category_id, "category_id"))
    if brand_id:
        stmt = stmt.where(Product.brand_id == _as_uuid(brand_id, "brand_id"))
    if gender:
        stmt = stmt.where(Product.gender == gender)
    if fit:
        stmt = stmt.where(Product.fit == fit)
    if season:
        stmt = stmt.where(Product.season == season)
    if price_min is not None:
        stmt = stmt.where(Product.price >= price_min)
    if price_max is not None:
        stmt = stmt.where(Product.price <= price_max)

    # filtros por variantes (join semántico)
    if color or size:
        pv = ProductVariant
        v_filters = [pv.active == True]  # noqa: E712
        if color:
            v_filters.append(func.lower(pv.color_name) == func.lower(color))
        if size:
            v_filters.append(func.lower(pv.size_label) == func.lower(size))
        stmt = stmt.join(pv, pv.product_id == Product.id).where(and_(*v_filters)).distinct()

    stmt = stmt.order_by(Product.created_at.desc()).offset(skip).limit(limit)
    return db.execute(stmt).scalars().all()

def get_product_by_slug(db: Session, slug: str) -> Product | None:
    return db.query(Product).filter(Product.slug == slug, Product.active == True).first()  # noqa: E712

def get_product_by_id(db: Session, product_id: str) -> Product | None:
    return db.get(Product, _as_uuid(product_id, "product_id"))

# ---------- Admin: CRUD producto ----------
def create_product(db: Session, payload: ProductCreate) -> Product:
    base_data = payload.model_dump(exclude={"variants", "images"})

    # --- slug ---
    raw_slug = (base_data.get("slug") or "").strip()
    base_slug = _slugify(raw_slug or base_data["title"])
    if _slug_exists(db, base_slug):
        raise HTTPException(status_code=400, detail="Product slug already exists")

    # --- separar FKs y normalizar a UUID ---
    raw_category_id = base_data.pop("category_id", None)
    raw_brand_id    = base_data.pop("brand_id", None)
    category_uuid = _as_uuid(raw_category_id, "category_id")
    brand_uuid    = _as_uuid(raw_brand_id, "brand_id")

    base_data.pop("slug", None)

    prod = Product(**base_data, slug=base_slug)
    prod.category_id = category_uuid
    prod.brand_id = brand_uuid

    db.add(prod)
    db.flush()  # obtener id para hijos

    # variants
    for v in payload.variants:
        var = ProductVariant(product_id=prod.id, **v.model_dump())
        db.add(var)

    # images
    for i in payload.images:
        img = ProductImage(product_id=prod.id, **i.model_dump())
        db.add(img)

    db.commit()
    db.refresh(prod)
    return prod

def update_product(db: Session, prod: Product, changes: ProductUpdate) -> Product:
    data = changes.model_dump(exclude_unset=True)

    if "category_id" in data:
        data["category_id"] = _as_uuid(data["category_id"], "category_id")
    if "brand_id" in data:
        data["brand_id"] = _as_uuid(data["brand_id"], "brand_id")

    if "slug" in data and data["slug"] is not None:
        new_slug = _slugify((data["slug"] or "").strip())
        if new_slug and new_slug != prod.slug and _slug_exists(db, new_slug):
            raise HTTPException(status_code=400, detail="Product slug already exists")
        data["slug"] = new_slug or prod.slug

    for k, v in data.items():
        setattr(prod, k, v)

    db.add(prod); db.commit(); db.refresh(prod)
    return prod

# ---------- Admin: Variants ----------
def add_variant(db: Session, product_id: str, data: ProductVariantCreate) -> ProductVariant:
    if (
        data.stock_reserved is not None
        and data.stock_on_hand is not None
        and data.stock_reserved > data.stock_on_hand
    ):
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    payload = data.model_dump()
    payload["sku"] = payload["sku"].strip()
    if payload.get("barcode"): payload["barcode"] = payload["barcode"].strip()
    payload["size_label"] = payload["size_label"].strip()
    payload["color_name"] = payload["color_name"].strip()
    if payload.get("color_hex"): payload["color_hex"] = payload["color_hex"].strip()

    var = ProductVariant(
        product_id=_as_uuid(product_id, "product_id"),
        **payload
    )
    db.add(var)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="SKU ya existe")
    db.refresh(var)
    return var

def update_variant(db: Session, variant: ProductVariant, changes: ProductVariantUpdate) -> ProductVariant:
    payload = changes.model_dump(exclude_unset=True)

    new_on_hand = payload.get("stock_on_hand", variant.stock_on_hand)
    new_reserved = payload.get("stock_reserved", variant.stock_reserved)

    if new_on_hand is not None and new_on_hand < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved is not None and new_reserved < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved > new_on_hand:
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    for f, v in payload.items():
        setattr(variant, f, v)

    db.add(variant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Violación de integridad")
    db.refresh(variant)
    return variant

def get_variant(db: Session, variant_id: str) -> ProductVariant | None:
    return db.get(ProductVariant, _as_uuid(variant_id, "variant_id"))

def delete_variant(db: Session, variant: ProductVariant) -> None:
    db.delete(variant); db.commit()

# ---------- Admin: Stock ----------
def set_stock(db: Session, variant: ProductVariant, on_hand: int | None = None, reserved: int | None = None) -> ProductVariant:
    if on_hand is not None:
        if on_hand < 0:
            raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
        variant.stock_on_hand = on_hand
    if reserved is not None:
        if reserved < 0:
            raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
        if reserved > (variant.stock_on_hand if on_hand is None else on_hand):
            raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")
        variant.stock_reserved = reserved
    db.add(variant); db.commit(); db.refresh(variant)
    return variant

# ---------- Admin: Images ----------
def add_image(db: Session, product_id: str, data: ProductImageCreate) -> ProductImage:
    pid = _as_uuid(product_id, "product_id")

    existing = (
        db.query(ProductImage)
        .filter(ProductImage.product_id == pid)
        .order_by(ProductImage.sort_order.desc())
        .all()
    )
    has_images = len(existing) > 0
    max_sort = existing[0].sort_order if has_images else -1

    payload = data.model_dump()

    # evitar pasar HttpUrl a SQLite
    if payload.get("url") is not None:
        payload["url"] = str(payload["url"])

    if payload.get("sort_order") is None:
        payload["sort_order"] = max_sort + 1

    img = ProductImage(product_id=pid, **payload)
    db.add(img)
    db.flush()

    make_primary = (not has_images) or bool(payload.get("is_primary"))
    if make_primary:
        db.query(ProductImage).filter(ProductImage.product_id == pid).update({ProductImage.is_primary: False})
        db.query(ProductImage).filter(ProductImage.id == img.id).update({ProductImage.is_primary: True})

    db.commit()
    db.refresh(img)
    return img

def set_primary_image(db: Session, product: Product, image_id: str) -> Product:
    img = (
        db.query(ProductImage)
        .filter(
            ProductImage.id == _as_uuid(image_id, "image_id"),
            ProductImage.product_id == product.id,
        )
        .first()
    )
    if not img:
        raise HTTPException(status_code=404, detail="Image not found for this product")

    db.query(ProductImage).filter(ProductImage.product_id == product.id).update({ProductImage.is_primary: False})
    db.query(ProductImage).filter(ProductImage.id == img.id).update({ProductImage.is_primary: True})

    db.commit()
    db.refresh(product)
    return product

def list_products_with_total(
    db: Session,
    search: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Product], int]:
    stmt = select(Product).where(Product.active == True)  # noqa: E712

    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(Product.title.ilike(like), Product.description.ilike(like)))
    if category:
        stmt = stmt.where(Product.category_id == _as_uuid(category, "category"))
    if brand:
        stmt = stmt.where(Product.brand_id == _as_uuid(brand, "brand"))
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)

    base_subq = stmt.order_by(None).subquery()
    total = db.execute(select(func.count()).select_from(base_subq)).scalar_one()

    items = db.execute(
        stmt.order_by(Product.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    return items, total

# ---------- Movimientos ----------
def _log_movement(db: Session, variant: ProductVariant, mtype: str, qty: int, reason: str | None):
    # Insert crudo para evitar import del modelo y ciclos
    db.execute(
        text("""
            INSERT INTO inventory_movements (id, variant_id, quantity, type, reason)
            VALUES (:id, :variant_id, :quantity, :type, :reason)
        """),
        {
            "id": str(uuid.uuid4()),          # el modelo tenía default en ORM, no en DB; lo generamos aquí
            "variant_id": str(variant.id),    # aseguramos str/UUID
            "quantity": int(qty),
            "type": mtype,
            "reason": reason,
        },
    )


def receive_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    variant.stock_on_hand += quantity
    db.add(variant)
    _log_movement(db, variant, "receive", quantity, reason)
    db.commit(); db.refresh(variant)
    return variant

def adjust_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    new_on_hand = variant.stock_on_hand + quantity
    if new_on_hand < 0:
        raise HTTPException(status_code=400, detail="No puede quedar negativo")
    variant.stock_on_hand = new_on_hand
    db.add(variant)
    _log_movement(db, variant, "adjust", abs(quantity), reason)
    db.commit(); db.refresh(variant)
    return variant

def reserve_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if variant.stock_reserved + quantity > variant.stock_on_hand:
        raise HTTPException(status_code=400, detail="No hay stock suficiente para reservar")
    variant.stock_reserved += quantity
    db.add(variant)
    _log_movement(db, variant, "reserve", quantity, reason)
    db.commit(); db.refresh(variant)
    return variant

def release_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if quantity > variant.stock_reserved:
        raise HTTPException(status_code=400, detail="No hay reservado suficiente")
    variant.stock_reserved -= quantity
    db.add(variant)
    _log_movement(db, variant, "release", quantity, reason)
    db.commit(); db.refresh(variant)
    return variant

def commit_sale(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="quantity debe ser > 0")
    if quantity > variant.stock_reserved:
        if quantity > variant.stock_on_hand:
            raise HTTPException(status_code=400, detail="No hay stock suficiente para la venta")
        variant.stock_on_hand -= quantity
    else:
        variant.stock_reserved -= quantity
        variant.stock_on_hand -= quantity

    if variant.stock_on_hand < 0:
        raise HTTPException(status_code=400, detail="No puede quedar negativo")

    db.add(variant)
    _log_movement(db, variant, "sale", quantity, reason)
    db.commit(); db.refresh(variant)
    return variant

def list_movements(db: Session, variant: ProductVariant, limit: int = 50, offset: int = 0):
    rows = db.execute(
        text("""
            SELECT id, type, quantity, reason, created_at
            FROM inventory_movements
            WHERE variant_id = :variant_id
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "variant_id": str(variant.id),
            "limit": int(limit),
            "offset": int(offset),
        },
    ).mappings().all()  # mappings() => dict-like
    # devolvemos una lista de dicts; MovementRead (UUID/datetime) los parsea sin problemas
    return [
        {
            "id": str(r["id"]),  # por si el driver devuelve UUID/Row proxy
            "type": r["type"],
            "quantity": int(r["quantity"]),
            "reason": r["reason"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---------- Quality ----------
def compute_product_quality(db: Session, product: Product) -> dict:
    points = 0
    issues: list[str] = []

    # imágenes
    imgs = db.query(ProductImage).filter(ProductImage.product_id == product.id).all()
    if imgs:
        points += 20
        if any(i.is_primary for i in imgs):
            points += 10
        else:
            issues.append("Falta imagen principal")
    else:
        issues.append("Sin imágenes")

    # descripción
    if (product.description or "") and len(product.description.strip()) >= 50:
        points += 25
    else:
        issues.append("Descripción corta o ausente (>=50)")

    # variantes
    vars = db.query(ProductVariant).filter(
        ProductVariant.product_id == product.id,
        ProductVariant.active == True  # noqa: E712
    ).all()
    if vars:
        points += 20
    else:
        issues.append("No hay variantes activas")

    # precio + moneda
    if product.price is not None and product.currency:
        points += 20
    else:
        issues.append("Falta precio o currency")

    # título
    if product.title and len(product.title.strip()) >= 8:
        points += 5
    else:
        issues.append("Título muy corto")

    score = min(points, 100)
    return {"score": score, "issues": issues}


# ---------- Admin: Stock Movements ----------
def _ensure_movements_table(db: Session):
    """Garantiza que inventory_movements exista (útil en tests SQLite sin migraciones)."""
    try:
        dialect = db.bind.dialect.name
    except Exception:
        dialect = "unknown"

    if dialect == "sqlite":
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS inventory_movements (
                id TEXT PRIMARY KEY,
                variant_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                type VARCHAR(50) NOT NULL,
                reason VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
    else:
        insp = inspect(db.bind)
        if "inventory_movements" not in insp.get_table_names():
            try:
                from app.models.inventory import InventoryMovement
                InventoryMovement.__table__.create(bind=db.bind, checkfirst=True)
            except Exception:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS inventory_movements (
                        id UUID PRIMARY KEY,
                        variant_id UUID NOT NULL,
                        quantity INTEGER NOT NULL,
                        type VARCHAR(50) NOT NULL,
                        reason VARCHAR(255),
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """))

def _log_movement(db: Session, variant: ProductVariant, mtype: str, qty: int, reason: str | None):
    _ensure_movements_table(db)  # 👈 se asegura que la tabla exista antes de insertar
    db.execute(
        text("""
            INSERT INTO inventory_movements (id, variant_id, quantity, type, reason)
            VALUES (:id, :variant_id, :quantity, :type, :reason)
        """),
        {
            "id": str(uuid.uuid4()),
            "variant_id": str(variant.id),
            "quantity": int(qty),
            "type": mtype,
            "reason": reason,
        },
    )