from fastapi import APIRouter, Depends, Query, Path, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.schemas.product import (
    ProductRead, ProductCreate, ProductUpdate,
    ProductVariantRead, ProductVariantCreate, ProductVariantUpdate,
    ProductImageRead, ProductImageCreate,
)
from math import ceil  # <-- agregar
from app.schemas.pagination import PaginatedProducts  # <-- nuevo
from app.models.product import Product, ProductVariant, ProductImage
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])

# ---------- Público ----------
@router.get("", response_model=PaginatedProducts)
def public_list(
    search: str | None = Query(None, description="texto a buscar"),
    category: str | None = Query(None, description="UUID de categoría"),
    brand: str | None = Query(None, description="UUID de marca"),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = product_service.list_products_with_total(
        db=db,
        search=search,
        category=category,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        limit=limit,
        offset=offset,
    )
    page = (offset // limit) + 1 if limit else 1
    pages = ceil(total / limit) if limit else 1

    # Devolvemos ORM directamente; FastAPI + Pydantic hacen el modelado a ProductRead
    return {
        "total": total,
        "page": page,
        "pages": pages,
        "limit": limit,
        "items": items,
    }

@router.get("/{slug}", response_model=ProductRead)
def public_get(slug: str, db: Session = Depends(get_db)):
    prod = product_service.get_product_by_slug(db, slug)
    if not prod:
        raise HTTPException(404, "Product not found")
    return prod

# ---------- Admin: Producto ----------
@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_admin)])
def admin_create(payload: ProductCreate, db: Session = Depends(get_db)):
    return product_service.create_product(db, payload)

@router.put("/{product_id}", response_model=ProductRead, dependencies=[Depends(get_current_admin)])
def admin_update(
    product_id: str = Path(...),
    payload: ProductUpdate = ...,
    db: Session = Depends(get_db),
):
    prod = product_service.get_product_by_id(db, product_id)
    if not prod:
        raise HTTPException(404, "Product not found")
    return product_service.update_product(db, prod, payload)

# ---------- Admin: Variants ----------
@router.post("/{product_id}/variants", response_model=ProductVariantRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_admin)])
def admin_add_variant(product_id: str, payload: ProductVariantCreate, db: Session = Depends(get_db)):
    prod = product_service.get_product_by_id(db, product_id)
    if not prod:
        raise HTTPException(404, "Product not found")
    return product_service.add_variant(db, product_id, payload)

@router.put("/variants/{variant_id}", response_model=ProductVariantRead, dependencies=[Depends(get_current_admin)])
def admin_update_variant(variant_id: str, payload: ProductVariantUpdate, db: Session = Depends(get_db)):
    var = product_service.get_variant(db, variant_id)
    if not var:
        raise HTTPException(404, "Variant not found")
    return product_service.update_variant(db, var, payload)

@router.delete("/variants/{variant_id}", status_code=204, dependencies=[Depends(get_current_admin)])
def admin_delete_variant(variant_id: str, db: Session = Depends(get_db)):
    var = product_service.get_variant(db, variant_id)
    if not var:
        raise HTTPException(404, "Variant not found")
    product_service.delete_variant(db, var)
    return

# ---------- Admin: Stock ----------
@router.patch("/variants/{variant_id}/stock", response_model=ProductVariantRead, dependencies=[Depends(get_current_admin)])
def admin_set_stock(
    variant_id: str,
    on_hand: int | None = Query(None, ge=0),
    reserved: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    var = product_service.get_variant(db, variant_id)
    if not var:
        raise HTTPException(404, "Variant not found")
    return product_service.set_stock(db, var, on_hand, reserved)

# ---------- Admin: Imágenes ----------
@router.post("/{product_id}/images", response_model=ProductImageRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_admin)])
def admin_add_image(product_id: str, payload: ProductImageCreate, db: Session = Depends(get_db)):
    prod = product_service.get_product_by_id(db, product_id)
    if not prod:
        raise HTTPException(404, "Product not found")
    return product_service.add_image(db, product_id, payload)

@router.post("/{product_id}/images/{image_id}/primary", response_model=ProductRead, dependencies=[Depends(get_current_admin)])
def admin_set_primary_image(product_id: str, image_id: str, db: Session = Depends(get_db)):
    prod = product_service.get_product_by_id(db, product_id)
    if not prod:
        raise HTTPException(404, "Product not found")
    return product_service.set_primary_image(db, prod, image_id)
