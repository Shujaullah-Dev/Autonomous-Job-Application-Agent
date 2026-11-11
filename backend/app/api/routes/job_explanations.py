
"""Day 14: Read-only, grounded LangChain explanations API."""

import logging
import uuid
from typing import Annotated

from app.api.routes.jobs import require_dev_write_key
from app.core.config import settings
from app.db.session import get_db
from app.schemas.job_explanation import JobExplanationResponse
from app.services.explanation_context import (
    CandidateNotFoundError,
    IncompleteCandidateProfileError,
    RecommendationNotFoundError,
    load_explanation_context,
)
from app.services.langchain_explanations import explain_evidence
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
)
from langchain_groq import ChatGroq
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["LangChain Explanations"],
    dependencies=[Depends(require_dev_write_key)],
)


@router.get(
    "/{candidate_id}/recommendations/{job_id}/explanation",
    response_model=JobExplanationResponse,
)
def get_job_explanation(
    candidate_id: uuid.UUID,
    job_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
    use_ai: bool = False,
) -> JobExplanationResponse:
    """
    Explain recommendation evidence.

    Default: deterministic explanation.
    Optional: LangChain + Groq, with fallback.
    """

    try:
        context = load_explanation_context(
            db,
            candidate_id=candidate_id,
            job_id=job_id,
        )

    except CandidateNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except IncompleteCandidateProfileError:
        raise HTTPException(
            status_code=409,
            detail="Candidate matching profile is incomplete",
        ) from None

    except RecommendationNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Job is not available for recommendation",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

    model = None

    if (
        use_ai
        and settings.langchain_explanations_enabled
        and settings.groq_api_key
    ):
        try:
            model = ChatGroq(
                model=settings.groq_model,
                api_key=settings.groq_api_key,
                temperature=0,
                timeout=settings.groq_timeout_seconds,
                max_retries=0,
                max_tokens=256,
            )

        except Exception as exc:
            # Do not expose credentials or request contents.
            logger.warning(
                "Could not initialize explanation model: %s",
                type(exc).__name__,
            )

    result = explain_evidence(
        context,
        use_ai=use_ai,
        model=model,
    )

    return JobExplanationResponse(
        candidate_id=candidate_id,
        job_id=context.job_id,
        job_title=context.job_title,
        score=context.score,
        scoring_mode="rules",
        explanation_mode=result.mode,
        llm_used=result.llm_used,
        model_name=(
            settings.groq_model
            if result.llm_used
            else None
        ),
        summary=result.summary,
        reasons=list(result.reasons),
        cautions=list(result.cautions),
        warnings=list(result.warnings),
    )