from uuid import UUID
from math import ceil
from typing import List

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status, Security
from sqlalchemy.orm import Session

# Se corrigen y unifican las importaciones
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.inventory import MovementCreate, MovementRead
from app.schemas.pagination import PaginatedProducts
from app.schemas.product import (
    ProductCreate,
    ProductImageCreate,
    ProductImageRead,
    ProductRead,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantRead,
    ProductVariantUpdate,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])

# ---------- Endpoints Públicos (sin seguridad) ----------
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
    page = (offset // limit) + 1
    pages = ceil(total / limit) if total else 1

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
        raise HTTPException(status_code=404, detail="Product not found")
    return prod


# ---------- Admin: Producto (requiere scope 'products:write') ----------
@router.post(
    "",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
)
def admin_create(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    return product_service.create_product(db, payload)


@router.put(
    "/{product_id}",
    response_model=ProductRead,
)
def admin_update(
    product_id: UUID = Path(..., description="UUID del producto"),
    payload: ProductUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    prod = product_service.get_product_by_id(db, str(product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_service.update_product(db, prod, payload)


# ---------- Admin: Variantes (requiere scope 'products:write') ----------
@router.post(
    "/{product_id}/variants",
    response_model=ProductVariantRead,
    status_code=status.HTTP_201_CREATED,
)
def admin_add_variant(
    product_id: UUID = Path(..., description="UUID del producto"),
    payload: ProductVariantCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    prod = product_service.get_product_by_id(db, str(product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_service.add_variant(db, str(product_id), payload)


@router.put(
    "/variants/{variant_id}",
    response_model=ProductVariantRead,
)
def admin_update_variant(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    payload: ProductVariantUpdate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    return product_service.update_variant(db, var, payload)


@router.delete(
    "/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def admin_delete_variant(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    product_service.delete_variant(db, var)
    return


# ---------- Admin: Imágenes (requiere scope 'products:write') ----------
@router.post(
    "/{product_id}/images",
    response_model=ProductImageRead,
    status_code=status.HTTP_201_CREATED,
)
def admin_add_image(
    product_id: UUID = Path(..., description="UUID del producto"),
    payload: ProductImageCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    prod = product_service.get_product_by_id(db, str(product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_service.add_image(db, str(product_id), payload)


@router.post(
    "/{product_id}/images/{image_id}/primary",
    response_model=ProductRead,
)
def admin_set_primary_image(
    product_id: UUID = Path(..., description="UUID del producto"),
    image_id: UUID = Path(..., description="UUID de la imagen"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    prod = product_service.get_product_by_id(db, str(product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_service.set_primary_image(db, prod, str(image_id))


# ---------- Admin: Movimientos de Inventario (requiere scope 'products:write') ----------
@router.patch(
    "/variants/{variant_id}/stock",
    response_model=ProductVariantRead,
)
def admin_set_stock(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    on_hand: int | None = Query(None, ge=0),
    reserved: int | None = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    return product_service.set_stock(db, var, on_hand, reserved)

# ... (El resto de los endpoints de movimientos de stock siguen el mismo patrón)

@router.post(
    "/variants/{variant_id}/stock/receive",
    response_model=ProductVariantRead,
)
def admin_receive_stock(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    payload: MovementCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    if payload.type != "receive":
        raise HTTPException(status_code=400, detail="type debe ser 'receive'")
    return product_service.receive_stock(db, var, payload.quantity, payload.reason)

@router.post(
    "/variants/{variant_id}/stock/reserve",
    response_model=ProductVariantRead,
)
def admin_reserve_stock(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    payload: MovementCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    if payload.type != "reserve":
        raise HTTPException(status_code=400, detail="type debe ser 'reserve'")
    return product_service.reserve_stock(db, var, payload.quantity, payload.reason)

@router.post(
    "/variants/{variant_id}/stock/release",
    response_model=ProductVariantRead,
)
def admin_release_stock(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    payload: MovementCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    if payload.type != "release":
        raise HTTPException(status_code=400, detail="type debe ser 'release'")
    return product_service.release_stock(db, var, payload.quantity, payload.reason)

@router.post(
    "/variants/{variant_id}/stock/sale",
    response_model=ProductVariantRead,
)
def admin_commit_sale(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    payload: MovementCreate = ...,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    if payload.type != "sale":
        raise HTTPException(status_code=400, detail="type debe ser 'sale'")
    return product_service.commit_sale(db, var, payload.quantity, payload.reason)

@router.post(
    "/variants/{variant_id}/stock/adjust",
    response_model=ProductVariantRead,
)
def admin_adjust_stock(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    delta: int = Query(...),
    reason: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:write"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    return product_service.adjust_stock(db, var, delta, reason)


# ---------- Admin: Lectura de Datos (requiere scope 'products:read') ----------
@router.get(
    "/variants/{variant_id}/stock/movements",
    response_model=List[MovementRead],
)
def admin_list_movements(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:read"]),
):
    var = product_service.get_variant(db, str(variant_id))
    if not var:
        raise HTTPException(status_code=404, detail="Variant not found")
    return product_service.list_movements(db, var, limit, offset)


@router.get(
    "/{product_id}/quality",
    response_model=dict,
)
def admin_product_quality(
    product_id: UUID = Path(..., description="UUID del producto"),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["products:read"]),
):
    prod = product_service.get_product_by_id(db, str(product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_service.compute_product_quality(db, prod)