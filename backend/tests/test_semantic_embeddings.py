
from types import SimpleNamespace

import numpy as np
import pytest
from app.services import semantic_embeddings as embeddings
from app.services.hybrid_matching import hybrid_score


def test_job_document_is_deterministic():
    inputs = {
        "title": "Backend Developer",
        "description": "Build Python APIs",
        "location": "Islamabad",
        "work_mode": "remote",
    }

    first = embeddings.job_document(**inputs)
    second = embeddings.job_document(**inputs)

    assert first == second
    assert embeddings.document_hash(first) == (
        embeddings.document_hash(second)
    )


def test_document_changes_update_hash():
    first = embeddings.job_document(
        title="Developer",
        description="Python",
        location=None,
        work_mode=None,
    )

    second = embeddings.job_document(
        title="Developer",
        description="Python and Docker",
        location=None,
        work_mode=None,
    )

    assert embeddings.document_hash(first) != (
        embeddings.document_hash(second)
    )


def test_candidate_document_uses_structured_data():
    candidate = SimpleNamespace(
        skills=["Python", "FastAPI"],
        titles=["Backend Developer"],
        years_experience=3,
        location="Islamabad",
    )

    text = embeddings.candidate_document(
        candidate,
        summary="Builds backend applications",
    )

    assert "Python" in text
    assert "Backend Developer" in text
    assert "3 years" in text
    assert "Builds backend applications" in text


def test_embedding_generation_without_model_download(monkeypatch):
    class FakeModel:
        def encode(self, texts, **kwargs):
            assert kwargs["normalize_embeddings"] is True

            return np.ones(
                (len(texts), 384),
                dtype=float,
            ) / np.sqrt(384)

    monkeypatch.setattr(
        embeddings,
        "_load_model",
        lambda: FakeModel(),
    )

    vectors = embeddings.embed_texts(
        ["Python backend developer", "SQL engineer"]
    )

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert all(np.isfinite(vectors[0]))


def test_empty_embedding_batch():
    assert embeddings.embed_texts([]) == []


def test_blank_text_rejected():
    with pytest.raises(ValueError):
        embeddings.embed_texts(["   "])


def test_hybrid_score():
    score, semantic = hybrid_score(80, 0.9)

    assert semantic == 90.0
    assert score == 83.0


def test_missing_embedding_uses_rules():
    score, semantic = hybrid_score(80, None)

    assert score == 80.0
    assert semantic is None


def test_negative_similarity_clamped():
    score, semantic = hybrid_score(80, -0.1)

    assert semantic == 0.0
    assert score == 56.0
