from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services import scoring_service

router = APIRouter(prefix="/internal/scoring", tags=["scoring"], include_in_schema=False)


@router.post("/run")
def run_scoring(db: Session = Depends(get_db)):
    result = scoring_service.run_scoring(db)
    return result


@router.get("/rankings")
def get_rankings(limit: int = 20, db: Session = Depends(get_db)):
    rankings = scoring_service.get_latest_rankings(db, limit)
    return [
        {
            "product_id": str(r.product_id),
            "popularity_score": float(r.popularity_score),
            "cold_score": float(r.cold_score),
            "profit_score": float(r.profit_score),
            "exposure_score": float(r.exposure_score),
            "computed_at": r.computed_at,
        }
        for r in rankings
    ]
