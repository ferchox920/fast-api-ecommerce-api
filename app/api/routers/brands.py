# app/api/routers/brands.py
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.services import brand_service
from app.models.product import Brand
from app.schemas.brand import BrandRead, BrandCreate, BrandUpdate

router = APIRouter(prefix="/brands", tags=["brands"])

# --- Público (paginado) ---
@router.get("", summary="List active brands (public)")
def public_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Devuelve solo marcas activas, con paginación.
    Respuesta:
    {
      "items": [BrandRead, ...],
      "total": <int>,
      "page": <int>,
      "page_size": <int>
    }
    """
    q = db.query(Brand).filter(Brand.active.is_(True))
    total = q.count()
    items = (
        q.order_by(Brand.name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [BrandRead.model_validate(b) for b in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

# --- Admin ---
@router.get("/all", response_model=list[BrandRead], dependencies=[Depends(get_current_admin)])
def admin_list(db: Session = Depends(get_db)):
    return brand_service.list_all_brands(db)

@router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_admin)])
def admin_create(payload: BrandCreate, db: Session = Depends(get_db)):
    return brand_service.create_brand(db, payload)

@router.put("/{brand_id}", response_model=BrandRead, dependencies=[Depends(get_current_admin)])
def admin_update(brand_id: str = Path(...), payload: BrandUpdate = ..., db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if not brand:
        raise HTTPException(404, "Brand not found")
    return brand_service.update_brand(db, brand, payload)
