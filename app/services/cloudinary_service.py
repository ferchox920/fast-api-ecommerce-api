"""Minimal Cloudinary integration used by the product image flows."""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from app.core.config import settings

try:  # pragma: no cover - optional dependency guard
    import cloudinary  # type: ignore
    import cloudinary.uploader  # type: ignore
except ImportError:  # pragma: no cover
    cloudinary = None  # type: ignore


logger = logging.getLogger(__name__)


def _library_available() -> bool:
    return cloudinary is not None


def is_configured() -> bool:
    """Return True when Cloudinary credentials and library are available."""
    return (
        _library_available()
        and bool(settings.CLOUD_NAME_CLOUDINARY)
        and bool(settings.API_KEY_CLOUDINARY)
        and bool(settings.API_SECRET_CLOUDINARY)
    )


@lru_cache(maxsize=1)
def _configure() -> bool:
    """Configure Cloudinary SDK once per process."""
    if not is_configured():
        return False
    assert cloudinary is not None  # for type checkers
    cloudinary.config(  # type: ignore[attr-defined]
        cloud_name=settings.CLOUD_NAME_CLOUDINARY,
        api_key=settings.API_KEY_CLOUDINARY,
        api_secret=settings.API_SECRET_CLOUDINARY,
        secure=settings.CLOUDINARY_SECURE_DELIVERY,
    )
    return True


async def upload_image_from_url(
    source_url: str,
    *,
    folder: Optional[str] = None,
    public_id: Optional[str] = None,
    extra_options: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Upload an image to Cloudinary from a publicly accessible URL.

    Returns the secure URL of the uploaded asset, or None if Cloudinary is not
    configured or the upload fails. The function runs the blocking upload in a
    worker thread to avoid blocking the event loop.
    """
    if not source_url or not is_configured():
        return None

    if not _configure():
        return None

    assert cloudinary is not None

    options: Dict[str, Any] = {"folder": folder or settings.CLOUDINARY_UPLOAD_FOLDER}
    if public_id:
        options["public_id"] = public_id
        options["overwrite"] = True
    if extra_options:
        options.update(extra_options)

    def _upload() -> Dict[str, Any]:
        return cloudinary.uploader.upload(source_url, **options)  # type: ignore[attr-defined]

    try:
        result = await asyncio.to_thread(_upload)
    except Exception as exc:  # pragma: no cover - network failures
        logger.warning("Cloudinary upload failed: %s", exc)
        return None

    return result.get("secure_url") or result.get("url")


__all__ = ["is_configured", "upload_image_from_url"]
