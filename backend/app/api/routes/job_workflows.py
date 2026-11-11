
"""Start, inspect and resume LangGraph workflows."""

import uuid

from app.api.routes.jobs import require_dev_write_key
from app.schemas.job_workflow import (
    WorkflowResponse,
    WorkflowReviewRequest,
    WorkflowStartRequest,
)
from app.services.explanation_context import (
    CandidateNotFoundError,
    IncompleteCandidateProfileError,
)
from app.services.job_workflow_graph import build_job_workflow
from app.services.workflow_recommendations import (
    load_workflow_recommendations,
)
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from langgraph.types import Command
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(
    prefix="/api/v1/candidates",
    tags=["LangGraph Workflows"],
    dependencies=[Depends(require_dev_write_key)],
)

# Shared within ONE development server process only.
_graph = build_job_workflow(load_workflow_recommendations)


def workflow_config(workflow_id: uuid.UUID) -> dict:
    return {
        "configurable": {
            "thread_id": str(workflow_id),
        }
    }


def workflow_response(
    candidate_id: uuid.UUID,
    workflow_id: uuid.UUID,
) -> WorkflowResponse:
    snapshot = _graph.get_state(
        workflow_config(workflow_id)
    )

    values = snapshot.values or {}

    # A workflow must belong to the requested candidate.
    # This is NOT a substitute for user authentication.
    if values.get("candidate_id") != str(candidate_id):
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    state = values["status"]

    messages = {
        "pending_review": (
            "Shortlist ready for review. "
            "No applications have been submitted."
        ),
        "approved": (
            "Shortlist selection recorded in workflow "
            "memory only. No applications submitted."
        ),
        "rejected": (
            "Shortlist rejected. No applications submitted."
        ),
        "no_matches": (
            "No jobs passed the selected filters and "
            "relevance threshold."
        ),
    }

    return WorkflowResponse(
        candidate_id=candidate_id,
        workflow_id=workflow_id,
        status=state,
        awaiting_review="review" in snapshot.next,
        shortlist=values.get("shortlist", []),
        approved_job_ids=values.get(
            "approved_job_ids", []
        ),
        message=messages[state],
    )


@router.post(
    "/{candidate_id}/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_workflow(
    candidate_id: uuid.UUID,
    payload: WorkflowStartRequest,
) -> WorkflowResponse:
    workflow_id = uuid.uuid4()

    initial_state = {
        "candidate_id": str(candidate_id),
        "options": payload.model_dump(),
    }

    try:
        _graph.invoke(
            initial_state,
            workflow_config(workflow_id),
        )

    except CandidateNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Candidate not found",
        ) from None

    except IncompleteCandidateProfileError:
        raise HTTPException(
            status_code=409,
            detail="Candidate profile has no matching evidence",
        ) from None

    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from None

    return workflow_response(
        candidate_id,
        workflow_id,
    )


@router.get(
    "/{candidate_id}/workflows/{workflow_id}",
    response_model=WorkflowResponse,
)
def get_workflow_status(
    candidate_id: uuid.UUID,
    workflow_id: uuid.UUID,
) -> WorkflowResponse:
    return workflow_response(
        candidate_id,
        workflow_id,
    )


@router.post(
    "/{candidate_id}/workflows/{workflow_id}/review",
    response_model=WorkflowResponse,
)
def review_workflow(
    candidate_id: uuid.UUID,
    workflow_id: uuid.UUID,
    payload: WorkflowReviewRequest,
) -> WorkflowResponse:
    current = workflow_response(
        candidate_id,
        workflow_id,
    )

    if not current.awaiting_review:
        raise HTTPException(
            status_code=409,
            detail="Workflow is not awaiting review",
        )

    available_ids = {
        item.job_id
        for item in current.shortlist
    }

    if not set(
        payload.approved_job_ids
    ).issubset(available_ids):
        raise HTTPException(
            status_code=409,
            detail="Selected job is not in the shortlist",
        )

    _graph.invoke(
        Command(
            resume=payload.model_dump()
        ),
        workflow_config(workflow_id),
    )

    return workflow_response(
        candidate_id,
        workflow_id,
    )
