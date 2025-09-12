from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.models.product import Product, ProductVariant
from app.schemas.variant import VariantRead, VariantCreate, VariantUpdate
from app.services import variant_service

router = APIRouter(prefix="/products", tags=["variants"])


# --------- Público (listar variantes de un producto) ---------
@router.get("/{product_id}/variants", response_model=list[VariantRead])
def list_for_product(product_id: str = Path(...), db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product or not product.active:
        raise HTTPException(status_code=404, detail="Product not found")
    return variant_service.list_variants_for_product(db, product)


# --------- Admin: crear variante para un producto ---------
@router.post(
    "/{product_id}/variants",
    response_model=VariantRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
def create(
    product_id: str = Path(...),
    payload: VariantCreate = ...,
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return variant_service.create_variant(db, product, payload)


# --------- Admin: actualizar variante ---------
@router.put(
    "/variants/{variant_id}",
    response_model=VariantRead,
    dependencies=[Depends(get_current_admin)],
)
def update(
    variant_id: str = Path(...),
    payload: VariantUpdate = ...,
    db: Session = Depends(get_db),
):
    variant = db.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return variant_service.update_variant(db, variant, payload)


# --------- Admin: eliminar variante ---------
@router.delete(
    "/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin)],
)
def delete(variant_id: str = Path(...), db: Session = Depends(get_db)):
    variant = db.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    variant_service.delete_variant(db, variant)
    return
