
import uuid
from typing import Annotated

from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.schemas.resume_analysis import (
    ResumeAnalysisResponse,
)
from app.services.resume_analysis import analyze_resume_text
from app.services.resume_parser import (
    ResumeParsingError,
    extract_resume_text,
)
from app.services.resume_validation import (
    MAX_RESUME_SIZE,
    ResumeValidationError,
    validate_resume,
)
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
)
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Resumes"],
)


@router.post(
    "/{candidate_id}/resume/preview",
    response_model=ResumeAnalysisResponse,
    responses={
        404: {"description": "Candidate not found"},
        413: {"description": "Resume too large"},
        422: {"description": "Invalid or unreadable resume"},
    },
)
async def preview_resume_analysis(
    candidate_id: uuid.UUID,
    file: Annotated[UploadFile, File(...)],
    db: Session = Depends(get_db),
) -> ResumeAnalysisResponse:

    candidate = db.get(CandidateProfile, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    try:
        content = await file.read(MAX_RESUME_SIZE + 1)

        file_type = validate_resume(
            filename=file.filename,
            content_type=file.content_type,
            file_content=content,
        )

        text = extract_resume_text(
            file_content=content,
            file_type=file_type,
        )

        # Groq-first orchestration with automatic fallback.
        return analyze_resume_text(
            candidate_id=candidate_id,
            text=text,
        )

    except ResumeValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=str(exc),
        ) from exc

    except ResumeParsingError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()
