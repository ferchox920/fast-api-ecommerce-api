from pydantic import BaseModel
from typing import List
from app.schemas.product import ProductRead

class PaginatedProducts(BaseModel):
    total: int
    page: int
    pages: int
    limit: int
    items: List[ProductRead]
