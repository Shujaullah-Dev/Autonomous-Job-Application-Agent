
""" Stateful, human-reviewed job shortlist workflow."""

from collections.abc import Callable
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.services.langchain_explanations import (
    EvidenceContext,
    explain_evidence,
)


class WorkflowState(TypedDict, total=False):
    candidate_id: str
    options: dict[str, Any]
    candidates: list[dict[str, Any]]
    shortlist: list[dict[str, Any]]
    approved_job_ids: list[int]
    status: Literal[
        "pending_review",
        "approved",
        "rejected",
        "no_matches",
    ]


# A provider loads candidate-specific job recommendations.
# The real Supabase-backed implementation is Developer B's work.
RecommendationProvider = Callable[
    [WorkflowState],
    list[dict[str, Any]],
]


def validate_review(
    response: object,
    shortlist: list[dict[str, Any]],
) -> list[int]:
    """Only accept explicit choices from the shown shortlist."""

    if not isinstance(response, dict):
        raise ValueError("Review must be an object")

    decision = response.get("decision")
    selected = response.get("approved_job_ids")

    if decision not in {"approve", "reject"}:
        raise ValueError("Invalid review decision")

    if not isinstance(selected, list):
        raise ValueError("approved_job_ids must be a list")

    if any(
        type(job_id) is not int or job_id < 1
        for job_id in selected
    ):
        raise ValueError("Job IDs must be positive integers")

    if len(set(selected)) != len(selected):
        raise ValueError("Duplicate job IDs are not allowed")

    if decision == "reject":
        if selected:
            raise ValueError(
                "Rejected shortlists cannot have approved IDs"
            )
        return []

    if not selected:
        raise ValueError(
            "Approval requires at least one selected job"
        )

    available_ids = {
        item["job_id"]
        for item in shortlist
    }

    if not set(selected).issubset(available_ids):
        raise ValueError(
            "Selected job does not belong to the shortlist"
        )

    return selected


def build_job_workflow(
    provider: RecommendationProvider,
    *,
    checkpointer: Any | None = None,
):
    """
    Build a LangGraph with a human-review interrupt.

    No node sends an application or modifies the database.
    """

    def load_jobs(state: WorkflowState) -> dict[str, Any]:
        # The provider runs only at the initial execution.
        # It is not repeated when the review node resumes.
        jobs = provider(state)

        return {"candidates": jobs}

    def prepare_explanations(
        state: WorkflowState,
    ) -> dict[str, Any]:
        prepared: list[dict[str, Any]] = []

        for job in state.get("candidates", []):
            context = EvidenceContext(
                job_id=job["job_id"],
                job_title=job["title"],
                score=job["score"],
                reasons=tuple(job["reasons"]),
                cautions=tuple(job["cautions"]),
            )

            # Reuse Day 14 without making a Groq request.
            explanation = explain_evidence(
                context,
                use_ai=False,
            )

            prepared.append(
                {
                    **job,
                    "summary": explanation.summary,
                    "reasons": list(explanation.reasons),
                    "cautions": list(explanation.cautions),
                }
            )

        status = (
            "pending_review"
            if prepared
            else "no_matches"
        )

        return {
            "shortlist": prepared,
            "status": status,
            "approved_job_ids": [],
        }

    def choose_path(
        state: WorkflowState,
    ) -> Literal["review", "finish"]:
        if state.get("shortlist"):
            return "review"

        return "finish"

    def human_review(
        state: WorkflowState,
    ) -> dict[str, Any]:
        # IMPORTANT:
        # Do not perform database writes or network
        # side effects before this interrupt.
        #
        # LangGraph re-executes this node on resume.
        response = interrupt(
            {
                "type": "shortlist_review",
                "message": (
                    "Review this shortlist. Approval only "
                    "selects jobs for later preparation; "
                    "it does not submit applications."
                ),
                "job_ids": [
                    item["job_id"]
                    for item in state["shortlist"]
                ],
            }
        )

        approved_ids = validate_review(
            response,
            state["shortlist"],
        )

        return {
            "approved_job_ids": approved_ids,
            "status": (
                "approved"
                if approved_ids
                else "rejected"
            ),
        }

    builder = StateGraph(WorkflowState)

    builder.add_node("load_jobs", load_jobs)
    builder.add_node(
        "prepare_explanations",
        prepare_explanations,
    )
    builder.add_node("review", human_review)

    builder.add_edge(START, "load_jobs")
    builder.add_edge(
        "load_jobs",
        "prepare_explanations",
    )

    builder.add_conditional_edges(
        "prepare_explanations",
        choose_path,
        {
            "review": "review",
            "finish": END,
        },
    )

    builder.add_edge("review", END)

    memory = (
        checkpointer
        if checkpointer is not None
        else InMemorySaver()
    )

    return builder.compile(
        checkpointer=memory,
    )
