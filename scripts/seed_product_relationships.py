"""Seed script for product-related relationships (questions, wishes, promotions, inventory)."""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Sequence
import uuid

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import select

# Ensure models are registered for relationships
import app.models.inventory  # noqa: F401

from app.core.config import settings
from app.db.session_async import AsyncSessionLocal
from app.models.inventory import InventoryMovement
from app.models.product import Product, ProductVariant
from app.models.product_question import ProductQuestion
from app.models.promotion import Promotion, PromotionProduct
from app.models.user import User
from app.models.wish import Wish
from app.schemas.promotion import PromotionCreate
from app.schemas.product_question import QuestionCreate
from app.schemas.wish import WishCreate
from app.services import inventory_service, product_question_service, promotion_service
from scripts import seed_dev_products, seed_dev_users


@dataclass(frozen=True, slots=True)
class QuestionSeed:
    user_email: str
    content: str


@dataclass(frozen=True, slots=True)
class WishSeed:
    user_email: str
    desired_price: Decimal | None = None
    notify_discount: bool = True


@dataclass(frozen=True, slots=True)
class RestockSeed:
    sku: str
    quantity: int
    reason: str


@dataclass(frozen=True, slots=True)
class ProductRelationSeed:
    product_slug: str
    questions: Sequence[QuestionSeed] = field(default_factory=tuple)
    wishes: Sequence[WishSeed] = field(default_factory=tuple)
    restocks: Sequence[RestockSeed] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class PromotionSeed:
    name: str
    description: str | None
    type: str
    scope: str
    product_slugs: Sequence[str] = field(default_factory=tuple)
    category_slug: str | None = None
    benefits: dict = field(default_factory=dict)
    duration_days: int = 14


RELATION_SEEDS: tuple[ProductRelationSeed, ...] = (
    ProductRelationSeed(
        product_slug="campera-denim-classic",
        questions=(
            QuestionSeed(
                user_email="user1.dev@example.com",
                content="La campera trae forro desmontable?",
            ),
        ),
        wishes=(
            WishSeed(
                user_email="user2.dev@example.com",
                desired_price=Decimal("44999.00"),
            ),
        ),
        restocks=(
            RestockSeed(
                sku="DENIM-JACKET-BLU-M",
                quantity=5,
                reason="DEV_SEED_RESTOCK_DENIM",
            ),
        ),
    ),
    ProductRelationSeed(
        product_slug="mochila-urbana-impermeable",
        questions=(
            QuestionSeed(
                user_email="manager.dev@example.com",
                content="Que capacidad real tiene la mochila?",
            ),
        ),
        wishes=(
            WishSeed(
                user_email="admin.dev@example.com",
                desired_price=Decimal("26999.00"),
            ),
        ),
        restocks=(
            RestockSeed(
                sku="BACKPACK-GRY-UNI",
                quantity=8,
                reason="DEV_SEED_RESTOCK_BACKPACK",
            ),
        ),
    ),
    ProductRelationSeed(
        product_slug="remera-basica-organica",
        questions=(
            QuestionSeed(
                user_email="user2.dev@example.com",
                content="La tela es pre encogida?",
            ),
        ),
        wishes=(
            WishSeed(
                user_email="manager.dev@example.com",
                desired_price=Decimal("10999.00"),
            ),
        ),
        restocks=(
            RestockSeed(
                sku="TEE-WHT-S",
                quantity=12,
                reason="DEV_SEED_RESTOCK_TEE",
            ),
        ),
    ),
)


PROMOTION_SEEDS: tuple[PromotionSeed, ...] = (
    PromotionSeed(
        name="Winter Denim 10 OFF",
        description="Descuento promocional para la campera denim.",
        type="product",
        scope="product",
        product_slugs=("campera-denim-classic",),
        benefits={"discount_percent": 10},
        duration_days=21,
    ),
    PromotionSeed(
        name="Accesorios Weekend",
        description="Promo con envio gratis para accesorios seleccionados.",
        type="category",
        scope="category",
        category_slug="accessories",
        benefits={"free_shipping": True},
        duration_days=10,
    ),
)


async def _load_users(db, emails: set[str]) -> dict[str, User]:
    if not emails:
        return {}
    stmt = select(User).where(User.email.in_(sorted(emails)))
    users = (await db.execute(stmt)).scalars().all()
    return {user.email: user for user in users}


async def _load_products(db, slugs: set[str]) -> dict[str, Product]:
    if not slugs:
        return {}
    stmt = select(Product).where(Product.slug.in_(sorted(slugs)))
    products = (await db.execute(stmt)).scalars().all()
    return {product.slug: product for product in products}


async def _load_variants_by_sku(db, skus: set[str]) -> dict[str, ProductVariant]:
    if not skus:
        return {}
    stmt = select(ProductVariant).where(ProductVariant.sku.in_(sorted(skus)))
    variants = (await db.execute(stmt)).scalars().all()
    return {variant.sku: variant for variant in variants}


async def _create_questions(
    db,
    product: Product,
    seeds: Sequence[QuestionSeed],
    users: dict[str, User],
    logger: logging.Logger,
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for seed in seeds:
        user = users.get(seed.user_email)
        if not user:
            logger.warning("User %s not found; skipping question '%s'", seed.user_email, seed.content)
            skipped += 1
            continue

        stmt = select(ProductQuestion).where(
            ProductQuestion.product_id == product.id,
            ProductQuestion.content == seed.content,
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        payload = QuestionCreate(product_id=product.id, content=seed.content)
        await product_question_service.create_question(db, payload=payload, user=user)
        created += 1
    return created, skipped


async def _create_wishes(
    db,
    product: Product,
    seeds: Sequence[WishSeed],
    users: dict[str, User],
    logger: logging.Logger,
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for seed in seeds:
        user = users.get(seed.user_email)
        if not user:
            logger.warning("User %s not found; skipping wish", seed.user_email)
            skipped += 1
            continue
        payload = WishCreate(
            product_id=product.id,
            desired_price=seed.desired_price,
            notify_discount=seed.notify_discount,
        )
        stmt = select(Wish).where(Wish.user_id == str(user.id), Wish.product_id == product.id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            skipped += 1
            continue
        wish = Wish(
            user_id=str(user.id),
            product_id=product.id,
            desired_price=payload.desired_price,
            notify_discount=payload.notify_discount,
        )
        db.add(wish)
        await db.flush([wish])
        created += 1
    return created, skipped


async def _create_restock_movements(
    db,
    restocks: Sequence[RestockSeed],
    variants: dict[str, ProductVariant],
    logger: logging.Logger,
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for seed in restocks:
        variant = variants.get(seed.sku)
        if not variant:
            logger.warning("Variant %s not found; skipping restock", seed.sku)
            skipped += 1
            continue
        stmt = select(InventoryMovement).where(
            InventoryMovement.variant_id == variant.id,
            InventoryMovement.reason == seed.reason,
        )
        exists = (await db.execute(stmt)).scalar_one_or_none()
        if exists:
            skipped += 1
            continue
        await inventory_service.receive_stock(db, variant, seed.quantity, seed.reason)
        created += 1
    return created, skipped


async def _ensure_promotion_products(
    db,
    promotion: Promotion,
    product_ids: Sequence[uuid.UUID],
) -> None:
    if not product_ids:
        return
    existing_stmt = select(PromotionProduct).where(
        PromotionProduct.promotion_id == promotion.id,
        PromotionProduct.product_id.in_(product_ids),
    )
    existing = {row.product_id for row in (await db.execute(existing_stmt)).scalars().all()}
    for pid in product_ids:
        if pid in existing:
            continue
        db.add(PromotionProduct(promotion_id=promotion.id, product_id=pid))


async def _create_promotions(
    db,
    seeds: Sequence[PromotionSeed],
    products: dict[str, Product],
    logger: logging.Logger,
) -> tuple[int, int]:
    created = 0
    skipped = 0
    for seed in seeds:
        stmt = select(Promotion).where(Promotion.name == seed.name)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        product_ids = [products[slug].id for slug in seed.product_slugs if slug in products]
        missing = [slug for slug in seed.product_slugs if slug not in products]
        for slug in missing:
            logger.warning("Product slug %s not found for promotion %s", slug, seed.name)

        criteria: dict = {}
        if seed.scope == "product" and product_ids:
            criteria["product_ids"] = [str(pid) for pid in product_ids]
        if seed.scope == "category" and seed.category_slug:
            category = next((prod.category for prod in products.values() if prod.category and prod.category.slug == seed.category_slug), None)
            if category:
                criteria["category_ids"] = [str(category.id)]
            else:
                logger.warning("Category %s not found for promotion %s", seed.category_slug, seed.name)

        now = datetime.now(timezone.utc)
        payload = PromotionCreate(
            name=seed.name,
            description=seed.description,
            type=seed.type,
            scope=seed.scope,
            criteria=criteria,
            benefits=seed.benefits,
            start_at=now,
            end_at=now + timedelta(days=seed.duration_days),
        )
        promotion = await promotion_service.create_promotion(db, payload)
        await _ensure_promotion_products(db, promotion, product_ids)

        original_emit = promotion_service.emit_promotion_event
        promotion_service.emit_promotion_event = lambda *args, **kwargs: None  # type: ignore[assignment]
        try:
            await promotion_service.activate_promotion(db, promotion.id)
        finally:
            promotion_service.emit_promotion_event = original_emit  # type: ignore[assignment]
        created += 1
    return created, skipped


async def seed_product_relationships() -> None:
    logger = logging.getLogger("seed_product_relationships")
    logger.info("Starting relationship seed against %s", settings.ASYNC_DATABASE_URL)

    # Ensure base seeds exist
    await seed_dev_users.seed_dev_users()
    await seed_dev_products.seed_dev_products()

    async with AsyncSessionLocal() as session:
        question_users = {q.user_email for seed in RELATION_SEEDS for q in seed.questions}
        wish_users = {w.user_email for seed in RELATION_SEEDS for w in seed.wishes}
        all_user_emails = question_users.union(wish_users)

        product_slugs = {seed.product_slug for seed in RELATION_SEEDS}
        promotion_product_slugs = {slug for seed in PROMOTION_SEEDS for slug in seed.product_slugs}
        all_product_slugs = product_slugs.union(promotion_product_slugs)

        variant_skus = {restock.sku for seed in RELATION_SEEDS for restock in seed.restocks}

        users = await _load_users(session, all_user_emails)
        products = await _load_products(session, all_product_slugs)
        variants = await _load_variants_by_sku(session, variant_skus)

        total_questions = total_question_skipped = 0
        total_wishes = total_wish_skipped = 0
        total_restocks = total_restock_skipped = 0

        for seed in RELATION_SEEDS:
            product = products.get(seed.product_slug)
            if not product:
                logger.warning("Product %s not found; skipping relationships", seed.product_slug)
                continue

            created_q, skipped_q = await _create_questions(session, product, seed.questions, users, logger)
            created_w, skipped_w = await _create_wishes(session, product, seed.wishes, users, logger)
            created_r, skipped_r = await _create_restock_movements(session, seed.restocks, variants, logger)

            total_questions += created_q
            total_question_skipped += skipped_q
            total_wishes += created_w
            total_wish_skipped += skipped_w
            total_restocks += created_r
            total_restock_skipped += skipped_r

        promo_created, promo_skipped = await _create_promotions(session, PROMOTION_SEEDS, products, logger)

        await session.commit()

    logger.info(
        "Seed summary: %s questions (%s skipped), %s wishes (%s skipped), %s restocks (%s skipped), %s promotions (%s skipped)",
        total_questions,
        total_question_skipped,
        total_wishes,
        total_wish_skipped,
        total_restocks,
        total_restock_skipped,
        promo_created,
        promo_skipped,
    )


async def main() -> None:
    await seed_product_relationships()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
