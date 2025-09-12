from typing import Sequence
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException
import uuid
import re
import unicodedata

from app.models.product import Category
from app.schemas.product import CategoryCreate

# ---------------- Utils ----------------
def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-zA-Z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text.lower()

def _as_uuid(value: str | uuid.UUID | None, field: str) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(status_code=422, detail=f"Invalid UUID for {field}")

def _name_exists(db: Session, name: str) -> bool:
    return db.query(Category).filter(Category.name == name).first() is not None

def _slug_exists(db: Session, slug: str) -> bool:
    return db.query(Category).filter(Category.slug == slug).first() is not None

# ---------------- Lectura pública ----------------
def list_active_categories(db: Session) -> Sequence[Category]:
    stmt = select(Category).where(Category.active == True).order_by(Category.created_at.desc())  # noqa: E712
    return db.execute(stmt).scalars().all()

def list_all_categories(db: Session) -> Sequence[Category]:
    stmt = select(Category).order_by(Category.created_at.desc())
    return db.execute(stmt).scalars().all()

def get_category_by_id(db: Session, category_id: str) -> Category | None:
    return db.get(Category, _as_uuid(category_id, "category_id"))

def get_category_by_slug(db: Session, slug: str) -> Category | None:
    return db.query(Category).filter(Category.slug == slug, Category.active == True).first()  # noqa: E712

# ---------------- Admin CRUD ----------------
def create_category(db: Session, payload: CategoryCreate) -> Category:
    data = payload.model_dump()

    # slug opcional: generar desde name si no viene
    raw_slug = (data.get("slug") or "").strip()
    slug = _slugify(raw_slug or data["name"])

    # unicidad (capa de aplicación, además de unique en DB)
    if _name_exists(db, data["name"]):
        raise HTTPException(status_code=400, detail="Category name already exists")
    if _slug_exists(db, slug):
        raise HTTPException(status_code=400, detail="Category slug already exists")

    cat = Category(name=data["name"], slug=slug, description=data.get("description"))
    db.add(cat); db.commit(); db.refresh(cat)
    return cat

def update_category(db: Session, category: Category, name: str | None = None, slug: str | None = None, description: str | None = None, active: bool | None = None) -> Category:
    changes: dict = {}

    if name is not None and name != category.name:
        if _name_exists(db, name):
            raise HTTPException(status_code=400, detail="Category name already exists")
        changes["name"] = name

    if slug is not None:
        new_slug = _slugify(slug) if slug else _slugify(changes.get("name", category.name))
        if new_slug != category.slug and _slug_exists(db, new_slug):
            raise HTTPException(status_code=400, detail="Category slug already exists")
        changes["slug"] = new_slug

    if description is not None:
        changes["description"] = description
    if active is not None:
        changes["active"] = bool(active)

    for k, v in changes.items():
        setattr(category, k, v)

    db.add(category); db.commit(); db.refresh(category)
    return category

def delete_category(db: Session, category: Category) -> None:
    db.delete(category); db.commit()
