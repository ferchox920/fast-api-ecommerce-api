from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.operations import commit_async
from app.db.session_async import get_async_db
from app.api.deps import get_current_admin
from app.models.product import Product, ProductVariant
from app.schemas.variant import VariantRead, VariantCreate, VariantUpdate
from app.services.product_service import variants as variant_service

router = APIRouter(prefix="/products", tags=["variants"])


# --------- Público (listar variantes de un producto) ---------
@router.get("/{product_id}/variants", response_model=list[VariantRead])
async def list_for_product(
    product_id: UUID = Path(..., description="UUID del producto"),
    db: AsyncSession = Depends(get_async_db),
):
    product = await db.get(Product, product_id)
    if not product or not product.active:
        raise HTTPException(status_code=404, detail="Product not found")
    return await variant_service.list_variants_for_product(db, product)


# --------- Admin: crear variante para un producto ---------
@router.post(
    "/{product_id}/variants",
    response_model=VariantRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(get_current_admin)],
)
async def create(
    product_id: UUID = Path(..., description="UUID del producto"),
    payload: VariantCreate = ...,
    db: AsyncSession = Depends(get_async_db),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = await variant_service.create_variant(db, product, payload)
    await commit_async(db)
    return variant


# --------- Admin: actualizar variante ---------
@router.put(
    "/variants/{variant_id}",
    response_model=VariantRead,
    dependencies=[Depends(get_current_admin)],
)
async def update(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    payload: VariantUpdate = ...,
    db: AsyncSession = Depends(get_async_db),
):
    variant = await db.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    updated = await variant_service.update_variant(db, variant, payload)
    await commit_async(db)
    return updated


# --------- Admin: eliminar variante ---------
@router.delete(
    "/variants/{variant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(get_current_admin)],
)
async def delete(
    variant_id: UUID = Path(..., description="UUID de la variante"),
    db: AsyncSession = Depends(get_async_db),
):
    variant = await db.get(ProductVariant, variant_id)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    await variant_service.delete_variant(db, variant)
    await commit_async(db)
    return
