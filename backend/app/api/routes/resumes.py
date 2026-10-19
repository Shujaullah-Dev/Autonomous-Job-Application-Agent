
import uuid

from app.db.session import get_db
from app.models.candidate import CandidateProfile
from app.schemas.resume import ResumeUploadResponse
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
    status,
)
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["Resumes"],
)


@router.post(
    "/{candidate_id}/resume",
    response_model=ResumeUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_resume(
    candidate_id: uuid.UUID,
    file: UploadFile = File(...), # noqa: B008
    db: Session = Depends(get_db), # noqa: B008
) -> ResumeUploadResponse:

    candidate = db.get(CandidateProfile, candidate_id)

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        )

    try:
        file_content = await file.read(
            MAX_RESUME_SIZE + 1
        )

        file_type = validate_resume(
            filename=file.filename,
            content_type=file.content_type,
            file_content=file_content,
        )

        extracted_text = extract_resume_text(
            file_content=file_content,
            file_type=file_type,
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

    return ResumeUploadResponse(
        candidate_id=candidate_id,
        filename=file.filename or "",
        file_type=file_type,
        extracted_text=extracted_text,
        character_count=len(extracted_text),
        message="Resume text extracted successfully",
    )
