
import uuid

from app.db.session import get_db
from app.schemas.resume_import import (
    ResumeImportRequest,
    ResumeImportResponse,
)
from app.services.resume_import import (
    CandidateNotFoundError,
    import_reviewed_resume,
)
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Resume Import"],
)


@router.post(
    "/{candidate_id}/resume/import",
    response_model=ResumeImportResponse,
)
def import_resume(
    candidate_id: uuid.UUID,
    payload: ResumeImportRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> ResumeImportResponse:

    try:
        return import_reviewed_resume(
            db=db,
            candidate_id=candidate_id,
            payload=payload,
        )

    except CandidateNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except IntegrityError:
        raise HTTPException(
            status_code=409,
            detail="Import conflicts with existing data",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed",
        ) from None