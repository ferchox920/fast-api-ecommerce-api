import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")
    return text.lower()

async def generate_unique_slug(db: AsyncSession, model, base_text: str) -> str:
    slug = slugify(base_text)
    candidate = slug
    i = 2
    while True:
        result = await db.execute(select(model.slug).where(model.slug == candidate).limit(1))
        exists = result.scalar_one_or_none()
        if not exists:
            break
        candidate = f"{slug}-{i}"
        i += 1
    return candidate
