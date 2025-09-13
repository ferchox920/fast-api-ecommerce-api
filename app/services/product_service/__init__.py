# Re-exporta funciones para mantener compatibilidad:
from .read import (
    list_products,
    get_product_by_slug,
    get_product_by_id,
    list_products_with_total,
)

from .crud import (
    create_product,
    update_product,
)

from .variants import (
    add_variant,
    update_variant,
    get_variant,
    delete_variant,
    set_stock,
)

from .images import (
    add_image,
    set_primary_image,
)

from .inventory import (
    receive_stock,
    adjust_stock,
    reserve_stock,
    release_stock,
    commit_sale,
    list_movements,
)

from .quality import (
    compute_product_quality,
)

__all__ = [
    # read
    "list_products", "get_product_by_slug", "get_product_by_id", "list_products_with_total",
    # crud
    "create_product", "update_product",
    # variants
    "add_variant", "update_variant", "get_variant", "delete_variant", "set_stock",
    # images
    "add_image", "set_primary_image",
    # inventory
    "receive_stock", "adjust_stock", "reserve_stock", "release_stock", "commit_sale", "list_movements",
    # quality
    "compute_product_quality",
]
