# app/services/brand_service.py
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.models.product import Brand
from app.schemas.brand import BrandCreate, BrandUpdate
import uuid


def create_brand(db: Session, payload: BrandCreate) -> Brand:
    slug = payload.slug or slugify(payload.name)

    # pre-chequeo para evitar IntegrityError y responder 400 claro
    exists = (
        db.query(Brand)
        .filter(or_(Brand.name == payload.name, Brand.slug == slug))
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with the same name or slug already exists",
        )

    brand = Brand(
        id=uuid.uuid4(),
        name=payload.name,
        slug=slug,
        description=payload.description,
        active=payload.active,
    )
    db.add(brand)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with the same name or slug already exists",
        )
    db.refresh(brand)
    return brand


def list_brands(db: Session) -> list[Brand]:
    """Lista TODAS las brands (activas e inactivas), útil para admin."""
    return db.query(Brand).order_by(Brand.created_at.desc()).all()


def list_active_brands(db: Session) -> list[Brand]:
    """Lista solo brands activas (para endpoints públicos)."""
    return (
        db.query(Brand)
        .filter(Brand.active.is_(True))
        .order_by(Brand.name.asc())
        .all()
    )


def get_brand(db: Session, brand_id: uuid.UUID) -> Brand | None:
    return db.query(Brand).filter(Brand.id == brand_id).first()


def update_brand(db: Session, brand: Brand, changes: BrandUpdate) -> Brand:
    data = changes.model_dump(exclude_unset=True)

    if "name" in data and data["name"]:
        # si cambia el name y no se envía slug, recalculamos
        if "slug" not in data or not data["slug"]:
            data["slug"] = slugify(data["name"])

    for k, v in data.items():
        setattr(brand, k, v)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brand with the same name or slug already exists",
        )
    db.refresh(brand)
    return brand


def delete_brand(db: Session, brand: Brand) -> None:
    db.delete(brand)
    db.commit()


# Helper local por si no tenés utilidades aún
def slugify(text: str) -> str:
    import re
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-{2,}", "-", s)
    return s[:140]
