import re
import unicodedata
from sqlalchemy.orm import Session

def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-")
    return text.lower()

def generate_unique_slug(db: Session, model, base_text: str) -> str:
    slug = slugify(base_text)
    candidate = slug
    i = 2
    while db.query(model).filter(model.slug == candidate).first():
        candidate = f"{slug}-{i}"
        i += 1
    return candidate
