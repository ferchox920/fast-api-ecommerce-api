# app/services/product_service/quality.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, ProductImage, ProductVariant


async def compute_product_quality(db: AsyncSession, product: Product) -> dict:
    points = 0
    issues: list[str] = []

    images_result = await db.execute(
        select(ProductImage).where(ProductImage.product_id == product.id)
    )
    images = images_result.scalars().all()
    if images:
        points += 20
        if any(image.is_primary for image in images):
            points += 10
        else:
            issues.append("Falta imagen principal")
    else:
        issues.append("Sin imagenes")

    if (product.description or "") and len(product.description.strip()) >= 50:
        points += 25
    else:
        issues.append("Descripcion corta o ausente (>=50)")

    variants_result = await db.execute(
        select(ProductVariant).where(
            ProductVariant.product_id == product.id,
            ProductVariant.active == True,  # noqa: E712
        )
    )
    variants = variants_result.scalars().all()
    if variants:
        points += 20
    else:
        issues.append("No hay variantes activas")

    if product.price is not None and product.currency:
        points += 20
    else:
        issues.append("Falta precio o currency")

    if product.title and len(product.title.strip()) >= 8:
        points += 5
    else:
        issues.append("Titulo muy corto")

    score = min(points, 100)
    return {"score": score, "issues": issues}
