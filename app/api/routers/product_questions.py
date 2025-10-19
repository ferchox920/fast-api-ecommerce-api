from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Security, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_optional_user
from app.db.session_async import get_async_db
from app.models.user import User
from app.schemas.product_question import (
    QuestionCreate,
    QuestionRead,
    AnswerCreate,
    QuestionUpdateVisibility,
    QuestionBlockPayload,
)
from app.services import product_question_service


router = APIRouter(prefix="/products", tags=["product-questions"])


@router.get("/{product_id}/questions", response_model=list[QuestionRead])
async def list_product_questions(
    product_id: UUID,
    include_hidden: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if include_hidden and (not current_user or not current_user.is_superuser):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    questions = await product_question_service.list_questions(
        db,
        product_id=product_id,
        include_hidden=include_hidden,
    )
    return [QuestionRead.model_validate(q, from_attributes=True) for q in questions]


@router.post("/{product_id}/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
async def create_question(
    product_id: UUID,
    payload: QuestionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    payload = QuestionCreate(product_id=product_id, content=payload.content)
    try:
        question = await product_question_service.create_question(db, payload=payload, user=current_user)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return QuestionRead.model_validate(question, from_attributes=True)


@router.post("/questions/{question_id}/answer", response_model=QuestionRead)
async def answer_question(
    question_id: UUID,
    payload: AnswerCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    try:
        question = await product_question_service.create_answer(
            db,
            question_id=str(question_id),
            payload=payload,
            admin=current_user,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return QuestionRead.model_validate(question, from_attributes=True)


@router.patch("/questions/{question_id}/visibility", response_model=QuestionRead)
async def set_visibility(
    question_id: UUID,
    payload: QuestionUpdateVisibility,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    try:
        question = await product_question_service.set_visibility(db, question_id=str(question_id), payload=payload)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return QuestionRead.model_validate(question, from_attributes=True)


@router.patch("/questions/{question_id}/block", response_model=QuestionRead)
async def set_block(
    question_id: UUID,
    payload: QuestionBlockPayload,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    try:
        question = await product_question_service.set_block(db, question_id=str(question_id), payload=payload)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return QuestionRead.model_validate(question, from_attributes=True)
