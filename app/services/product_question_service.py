from __future__ import annotations

import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.product import Product
from app.models.user import User
from app.models.product_question import ProductQuestion, ProductAnswer, QuestionStatus
from app.schemas.product_question import (
    QuestionCreate,
    AnswerCreate,
    QuestionUpdateVisibility,
    QuestionBlockPayload,
)
from app.services import notification_service


def _as_uuid(value: str | uuid.UUID, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid UUID for {field}")


def list_questions(db: Session, product_id: uuid.UUID | None = None, include_hidden: bool = False):
    stmt = select(ProductQuestion).order_by(ProductQuestion.created_at.desc())
    if product_id:
        stmt = stmt.where(ProductQuestion.product_id == product_id)
    if not include_hidden:
        stmt = stmt.where(ProductQuestion.is_visible == True, ProductQuestion.is_blocked == False)  # noqa: E712
    return db.execute(stmt).scalars().all()


def create_question(db: Session, *, payload: QuestionCreate, user: User | None) -> ProductQuestion:
    product = db.get(Product, _as_uuid(payload.product_id, "product_id"))
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    question = ProductQuestion(
        product_id=product.id,
        user_id=user.id if user else None,
        content=payload.content,
    )
    db.add(question)
    db.commit()
    db.refresh(question)

    notification_service.notify_admin_new_question(db, question)
    return question


def create_answer(db: Session, *, question_id: str, payload: AnswerCreate, admin: User) -> ProductAnswer:
    question = db.get(ProductQuestion, _as_uuid(question_id, "question_id"))
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    if question.is_blocked:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Question is blocked")

    answer = ProductAnswer(
        question=question,
        admin_id=admin.id,
        content=payload.content,
    )
    db.add(answer)
    question.status = QuestionStatus.answered
    question.is_visible = True
    db.add(question)
    db.commit()
    db.refresh(answer)
    db.refresh(question)

    notification_service.notify_question_answer(db, question, answer)
    return answer


def set_visibility(db: Session, *, question_id: str, payload: QuestionUpdateVisibility) -> ProductQuestion:
    question = db.get(ProductQuestion, _as_uuid(question_id, "question_id"))
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    question.is_visible = payload.is_visible
    if not payload.is_visible:
        question.status = QuestionStatus.hidden
    elif question.status == QuestionStatus.hidden:
        question.status = QuestionStatus.pending
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def set_block(db: Session, *, question_id: str, payload: QuestionBlockPayload) -> ProductQuestion:
    question = db.get(ProductQuestion, _as_uuid(question_id, "question_id"))
    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question not found")
    question.is_blocked = payload.is_blocked
    if payload.is_blocked:
        question.status = QuestionStatus.blocked
        question.is_visible = False
    db.add(question)
    db.commit()
    db.refresh(question)
    return question
