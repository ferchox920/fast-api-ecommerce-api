from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Security, status, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.db.session import get_db
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
def list_product_questions(
    product_id: UUID,
    include_hidden: bool = False,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if include_hidden and (not current_user or not current_user.is_superuser):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
    questions = product_question_service.list_questions(
        db,
        product_id=product_id,
        include_hidden=include_hidden,
    )
    return questions


@router.post("/{product_id}/questions", response_model=QuestionRead, status_code=status.HTTP_201_CREATED)
def create_question(
    product_id: UUID,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    payload = QuestionCreate(product_id=product_id, content=payload.content)
    question = product_question_service.create_question(db, payload=payload, user=current_user)
    return question


@router.post("/questions/{question_id}/answer", response_model=QuestionRead)
def answer_question(
    question_id: UUID,
    payload: AnswerCreate,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    answer = product_question_service.create_answer(db, question_id=str(question_id), payload=payload, admin=current_user)
    return answer.question


@router.patch("/questions/{question_id}/visibility", response_model=QuestionRead)
def set_visibility(
    question_id: UUID,
    payload: QuestionUpdateVisibility,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    return product_question_service.set_visibility(db, question_id=str(question_id), payload=payload)


@router.patch("/questions/{question_id}/block", response_model=QuestionRead)
def set_block(
    question_id: UUID,
    payload: QuestionBlockPayload,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=["admin"]),
):
    return product_question_service.set_block(db, question_id=str(question_id), payload=payload)
