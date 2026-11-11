
"""Unit tests for LangGraph transitions."""

import uuid

import pytest
from app.services.job_workflow_graph import (
    build_job_workflow,
    validate_review,
)
from langgraph.types import Command


def fake_provider(state):
    return [
        {
            "job_id": 101,
            "title": "Python Backend Developer",
            "score": 82.0,
            "work_mode": "remote",
            "reasons": [
                "Python and FastAPI match the profile."
            ],
            "cautions": [
                "Hiring eligibility is unverified."
            ],
        },
        {
            "job_id": 102,
            "title": "AI Engineer",
            "score": 75.0,
            "work_mode": None,
            "reasons": [
                "Python matches the profile."
            ],
            "cautions": [
                "Work mode is unknown."
            ],
        },
    ]


def new_config():
    return {
        "configurable": {
            "thread_id": str(uuid.uuid4()),
        }
    }


def start(graph, config):
    return graph.invoke(
        {
            "candidate_id": str(uuid.uuid4()),
            "options": {
                "min_score": 50,
                "limit": 5,
            },
        },
        config,
    )


def test_workflow_pauses_for_human_review():
    graph = build_job_workflow(fake_provider)
    config = new_config()

    start(graph, config)

    snapshot = graph.get_state(config)

    assert snapshot.values["status"] == "pending_review"
    assert len(snapshot.values["shortlist"]) == 2
    assert "review" in snapshot.next
    assert snapshot.values["shortlist"][0]["summary"]


def test_approval_resumes_and_finishes():
    graph = build_job_workflow(fake_provider)
    config = new_config()

    start(graph, config)

    graph.invoke(
        Command(
            resume={
                "decision": "approve",
                "approved_job_ids": [101],
            }
        ),
        config,
    )

    snapshot = graph.get_state(config)

    assert snapshot.values["status"] == "approved"
    assert snapshot.values["approved_job_ids"] == [101]
    assert snapshot.next == ()


def test_rejection_finishes_without_selection():
    graph = build_job_workflow(fake_provider)
    config = new_config()

    start(graph, config)

    graph.invoke(
        Command(
            resume={
                "decision": "reject",
                "approved_job_ids": [],
            }
        ),
        config,
    )

    snapshot = graph.get_state(config)

    assert snapshot.values["status"] == "rejected"
    assert snapshot.values["approved_job_ids"] == []
    assert snapshot.next == ()


def test_no_matches_finishes_without_interrupt():
    graph = build_job_workflow(
        lambda state: []
    )
    config = new_config()

    start(graph, config)

    snapshot = graph.get_state(config)

    assert snapshot.values["status"] == "no_matches"
    assert snapshot.values["shortlist"] == []
    assert snapshot.next == ()


def test_invalid_job_selection_is_rejected():
    with pytest.raises(ValueError):
        validate_review(
            {
                "decision": "approve",
                "approved_job_ids": [999],
            },
            fake_provider({}),
        )


def test_duplicate_selection_is_rejected():
    with pytest.raises(ValueError):
        validate_review(
            {
                "decision": "approve",
                "approved_job_ids": [101, 101],
            },
            fake_provider({}),
        )


def test_boolean_job_id_is_rejected():
    with pytest.raises(ValueError):
        validate_review(
            {
                "decision": "approve",
                "approved_job_ids": [True],
            },
            fake_provider({}),
        )


def test_rejection_cannot_approve_jobs():
    with pytest.raises(ValueError):
        validate_review(
            {
                "decision": "reject",
                "approved_job_ids": [101],
            },
            fake_provider({}),
        )


def test_separate_threads_have_separate_state():
    graph = build_job_workflow(fake_provider)

    first = new_config()
    second = new_config()

    start(graph, first)
    start(graph, second)

    graph.invoke(
        Command(
            resume={
                "decision": "approve",
                "approved_job_ids": [101],
            }
        ),
        first,
    )

    assert graph.get_state(first).values["status"] == "approved"
    assert graph.get_state(second).values["status"] == (
        "pending_review"
    )
