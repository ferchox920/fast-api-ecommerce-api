from sqlalchemy.orm import Session
from app.models.product import Product, ProductVariant, ProductImage

def compute_product_quality(db: Session, product: Product) -> dict:
    points = 0
    issues: list[str] = []

    imgs = db.query(ProductImage).filter(ProductImage.product_id == product.id).all()
    if imgs:
        points += 20
        if any(i.is_primary for i in imgs):
            points += 10
        else:
            issues.append("Falta imagen principal")
    else:
        issues.append("Sin imágenes")

    if (product.description or "") and len(product.description.strip()) >= 50:
        points += 25
    else:
        issues.append("Descripción corta o ausente (>=50)")

    vars = db.query(ProductVariant).filter(
        ProductVariant.product_id == product.id,
        ProductVariant.active == True  # noqa: E712
    ).all()
    if vars:
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
        issues.append("Título muy corto")

    score = min(points, 100)
    return {"score": score, "issues": issues}
