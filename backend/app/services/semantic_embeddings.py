
"""Local sentence embeddings and deterministic text preparation."""

import hashlib
import math
from collections.abc import Sequence
from functools import lru_cache

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DIMENSIONS = 384


class EmbeddingError(RuntimeError):
    pass


def job_document(
    *,
    title: str,
    description: str,
    location: str | None,
    work_mode: str | None,
) -> str:
    """Create consistent text for a job embedding."""

    return (
        f"Job title: {title.strip()}\n"
        f"Location: {(location or 'Unknown').strip()}\n"
        f"Work mode: {work_mode or 'Unknown'}\n"
        f"Description: {description.strip()[:3000]}"
    )


def candidate_document(
    candidate,
    summary: str | None = None,
) -> str:
    """Use structured candidate information, excluding contact details."""

    skills = ", ".join(
        sorted(set(candidate.skills), key=str.casefold)
    )

    titles = ", ".join(
        dict.fromkeys(candidate.titles)
    )

    years = (
        f"{candidate.years_experience} years"
        if candidate.years_experience is not None
        else "Unknown"
    )

    return (
        f"Previous roles: {titles or 'Unknown'}\n"
        f"Skills: {skills or 'Unknown'}\n"
        f"Experience: {years}\n"
        f"Location: {candidate.location or 'Unknown'}\n"
        f"Profile summary: {(summary or '')[:2000]}"
    )


def document_hash(document: str) -> str:
    """Detect changes requiring an embedding refresh."""

    return hashlib.sha256(
        document.encode("utf-8")
    ).hexdigest()


@lru_cache(maxsize=1)
def _load_model():
    """Load the local embedding model only when needed."""

    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            MODEL_NAME,
            device="cpu",
        )
    except Exception as exc:
        raise EmbeddingError(
            "Could not initialize local embedding model"
        ) from exc


def embed_texts(
    texts: Sequence[str],
) -> list[list[float]]:
    """Generate normalized 384-dimensional vectors."""

    if not texts:
        return []

    if any(not text.strip() for text in texts):
        raise ValueError("Cannot embed blank text")

    try:
        encoded = _load_model().encode(
            list(texts),
            batch_size=8,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        vectors = encoded.tolist()

    except EmbeddingError:
        raise

    except Exception as exc:
        raise EmbeddingError(
            "Embedding generation failed"
        ) from exc

    if len(vectors) != len(texts):
        raise EmbeddingError(
            "Unexpected embedding batch shape"
        )

    for vector in vectors:
        if (
            len(vector) != DIMENSIONS
            or not all(
                math.isfinite(float(number))
                for number in vector
            )
            or not any(
                float(number) != 0
                for number in vector
            )
        ):
            raise EmbeddingError(
                "Invalid 384-dimensional embedding"
            )

    return vectors
