from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_admin
from app.services import category_service
from app.models.product import Category
from app.schemas.category import CategoryRead, CategoryCreate, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])

# --- Público ---
@router.get("", response_model=list[CategoryRead])
def public_list(db: Session = Depends(get_db)):
    return category_service.list_active_categories(db)

# --- Admin ---
@router.get("/all", response_model=list[CategoryRead], dependencies=[Depends(get_current_admin)])
def admin_list(db: Session = Depends(get_db)):
    return category_service.list_all_categories(db)

@router.post("", response_model=CategoryRead, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_admin)])
def admin_create(payload: CategoryCreate, db: Session = Depends(get_db)):
    return category_service.create_category(db, payload)

@router.put("/{category_id}", response_model=CategoryRead, dependencies=[Depends(get_current_admin)])
def admin_update(category_id: str = Path(...), payload: CategoryUpdate = ..., db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(404, "Category not found")
    return category_service.update_category(db, category, payload)
