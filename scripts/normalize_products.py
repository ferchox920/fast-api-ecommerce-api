"""Normalize development products by aligning them with the curated seeds."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

from app.core.config import settings
from app.db.session_async import AsyncSessionLocal
from app.models.product import Product
from scripts import seed_dev_products, seed_product_relationships
from app.services.product_service.utils import slugify


EXPECTED_SLUGS: set[str] = {
    seed.slug or slugify(seed.title)
    for seed in seed_dev_products.PRODUCTS
}
EXPECTED_SLUGS.update(seed.product_slug for seed in seed_product_relationships.RELATION_SEEDS)


async def normalize_products() -> None:
    logger = logging.getLogger("normalize_products")
    logger.info("Normalizing products for %s", settings.ASYNC_DATABASE_URL)

    await seed_dev_products.seed_dev_products()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Product))
        products = result.scalars().all()

        removed = 0
        for product in products:
            if product.slug not in EXPECTED_SLUGS:
                await session.delete(product)
                removed += 1
        await session.commit()

    logger.info(
        "Normalization complete. Removed %s products; kept %s curated slugs.",
        removed,
        len(EXPECTED_SLUGS),
    )


async def main() -> None:
    await normalize_products()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
