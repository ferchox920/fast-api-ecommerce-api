from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException
import unicodedata
import uuid
import re

from app.models.product import Product

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text.lower()

def slug_exists(db: Session, slug: str) -> bool:
    return db.query(Product).filter(Product.slug == slug).first() is not None

def as_uuid(value: str | uuid.UUID | None, field: str) -> Optional[uuid.UUID]:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid UUID for {field}")
