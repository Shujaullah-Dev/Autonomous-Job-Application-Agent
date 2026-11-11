
import json

from app.services.langchain_explanations import (
    EvidenceContext,
    explain_evidence,
    parse_selection,
)
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda


def context():
    return EvidenceContext(
        job_id=10,
        job_title="Python Backend Developer",
        score=72.5,
        reasons=(
            "Python matches the candidate profile.",
            "FastAPI matches the candidate profile.",
        ),
        cautions=(
            "Country eligibility is unverified.",
            "Salary period is unknown.",
        ),
    )


def fake_model(output):
    return RunnableLambda(
        lambda prompt: AIMessage(content=output)
    )


def test_deterministic_without_ai():
    result = explain_evidence(context())

    assert result.mode == "deterministic"
    assert result.llm_used is False
    assert result.reasons == context().reasons
    assert result.cautions == context().cautions


def test_langchain_reorders_existing_evidence():
    output = json.dumps(
        {
            "reason_order": [1, 0],
            "caution_order": [1, 0],
        }
    )

    result = explain_evidence(
        context(),
        use_ai=True,
        model=fake_model(output),
    )

    assert result.mode == "langchain_groq"
    assert result.llm_used is True

    assert result.reasons == (
        context().reasons[1],
        context().reasons[0],
    )

    assert result.cautions == (
        context().cautions[1],
        context().cautions[0],
    )


def test_invalid_json_uses_fallback():
    result = explain_evidence(
        context(),
        use_ai=True,
        model=fake_model("not valid JSON"),
    )

    assert result.mode == "fallback"
    assert result.llm_used is False
    assert result.reasons == context().reasons


def test_invented_reason_index_rejected():
    result = explain_evidence(
        context(),
        use_ai=True,
        model=fake_model(
            json.dumps(
                {
                    "reason_order": [0, 999],
                    "caution_order": [0, 1],
                }
            )
        ),
    )

    assert result.mode == "fallback"
    assert result.reasons == context().reasons


def test_dropped_caution_rejected():
    result = explain_evidence(
        context(),
        use_ai=True,
        model=fake_model(
            json.dumps(
                {
                    "reason_order": [0, 1],
                    "caution_order": [0],
                }
            )
        ),
    )

    assert result.mode == "fallback"
    assert len(result.cautions) == 2


def test_missing_model_uses_fallback():
    result = explain_evidence(
        context(),
        use_ai=True,
        model=None,
    )

    assert result.mode == "fallback"
    assert result.warnings


def test_exception_uses_fallback():
    def fail(prompt):
        raise RuntimeError("Simulated provider failure")

    result = explain_evidence(
        context(),
        use_ai=True,
        model=RunnableLambda(fail),
    )

    assert result.mode == "fallback"
    assert result.llm_used is False


def test_boolean_indices_rejected():
    try:
        parse_selection(
            json.dumps(
                {
                    "reason_order": [True, 0],
                    "caution_order": [0, 1],
                }
            ),
            reason_count=2,
            caution_count=2,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Boolean indices should be rejected"
        )


def test_no_ai_request_never_calls_model():
    def fail(prompt):
        raise AssertionError(
            "Model should not have been invoked"
        )

    result = explain_evidence(
        context(),
        use_ai=False,
        model=RunnableLambda(fail),
    )

    assert result.mode == "deterministic"