from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.product import ProductVariant
from app.services import inventory_service
from app.services.exceptions import ServiceError


def _commit_and_refresh(db: Session, variant: ProductVariant) -> ProductVariant:
    db.commit()
    db.refresh(variant)
    return variant


def receive_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    try:
        inventory_service.receive_stock(db, variant, quantity, reason)
        return _commit_and_refresh(db, variant)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)


def adjust_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    try:
        inventory_service.adjust_stock(db, variant, quantity, reason)
        return _commit_and_refresh(db, variant)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)


def reserve_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    try:
        inventory_service.reserve_stock(db, variant, quantity, reason)
        return _commit_and_refresh(db, variant)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)


def release_stock(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    try:
        inventory_service.release_stock(db, variant, quantity, reason)
        return _commit_and_refresh(db, variant)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)


def commit_sale(db: Session, variant: ProductVariant, quantity: int, reason: str | None = None) -> ProductVariant:
    try:
        inventory_service.commit_sale(db, variant, quantity, reason)
        return _commit_and_refresh(db, variant)
    except ServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.detail)


def list_movements(db: Session, variant: ProductVariant, limit: int = 50, offset: int = 0):
    return inventory_service.list_movements(db, variant, limit, offset)
