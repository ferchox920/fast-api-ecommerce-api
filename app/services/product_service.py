from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func
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

# ---------------- Utils: slug ----------------
def _slugify(text: str) -> str:
    # Normaliza, quita acentos y símbolos, y pasa a kebab-case
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
    # Política del test: título repetido -> mismo slug -> debe fallar (400)
    if _slug_exists(db, base_slug):
        raise HTTPException(status_code=400, detail="Product slug already exists")

    # --- separar FKs y normalizar a UUID ---
    raw_category_id = base_data.pop("category_id", None)
    raw_brand_id    = base_data.pop("brand_id", None)
    category_uuid = _as_uuid(raw_category_id, "category_id")
    brand_uuid    = _as_uuid(raw_brand_id, "brand_id")

    # evitar duplicar el argumento slug
    base_data.pop("slug", None)

    # crear producto SIN las FKs primero
    prod = Product(**base_data, slug=base_slug)

    # asignar FKs ya como uuid.UUID
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

    # Coerción a UUID si actualizan FKs
    if "category_id" in data:
        data["category_id"] = _as_uuid(data["category_id"], "category_id")
    if "brand_id" in data:
        data["brand_id"] = _as_uuid(data["brand_id"], "brand_id")

    # Si actualizan el slug, normalizar y validar unicidad (si lo cambian efectivamente)
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
    # Validación de stock
    if (
        data.stock_reserved is not None
        and data.stock_on_hand is not None
        and data.stock_reserved > data.stock_on_hand
    ):
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    # Normalizaciones simples
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
        # SKU único
        raise HTTPException(status_code=400, detail="SKU ya existe")
    db.refresh(var)
    return var

def update_variant(db: Session, variant: ProductVariant, changes: ProductVariantUpdate) -> ProductVariant:
    payload = changes.model_dump(exclude_unset=True)

    # Calcular nuevos stocks para validar coherencia
    new_on_hand = payload.get("stock_on_hand", variant.stock_on_hand)
    new_reserved = payload.get("stock_reserved", variant.stock_reserved)

    if new_on_hand is not None and new_on_hand < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved is not None and new_reserved < 0:
        raise HTTPException(status_code=400, detail="Stock no puede ser negativo")
    if new_reserved > new_on_hand:
        raise HTTPException(status_code=400, detail="stock_reserved no puede exceder stock_on_hand")

    # Actualizar campos
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
    img = ProductImage(product_id=_as_uuid(product_id, "product_id"), **data.model_dump())
    db.add(img); db.commit(); db.refresh(img)
    return img

def set_primary_image(db: Session, product: Product, image_id: str) -> Product:
    # desmarcar todas y marcar una
    db.query(ProductImage).filter(ProductImage.product_id == product.id).update({ProductImage.is_primary: False})
    db.query(ProductImage).filter(
        ProductImage.id == _as_uuid(image_id, "image_id"),
        ProductImage.product_id == product.id
    ).update({ProductImage.is_primary: True})
    db.commit(); db.refresh(product)
    return product
