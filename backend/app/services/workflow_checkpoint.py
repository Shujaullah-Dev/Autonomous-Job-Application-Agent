"""Select durable LangGraph checkpoint storage.

The workflow graph keeps pending shortlist reviews in a checkpointer. The
in-process saver loses them when the API restarts, so a PostgreSQL-backed
saver is used whenever ``LANGGRAPH_CHECKPOINT_URL`` is configured.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

POSTGRES_PREFIXES = ("postgresql://", "postgres://", "postgresql+psycopg://")


class CheckpointUnavailable(RuntimeError):
    """Configured durable checkpoint storage could not be created."""


def build_workflow_checkpointer() -> Any | None:
    """Return a PostgreSQL saver, or ``None`` for the in-process default."""

    url = settings.langgraph_checkpoint_url.strip()

    if not url:
        return None

    if not url.startswith(POSTGRES_PREFIXES):
        raise CheckpointUnavailable(
            "LANGGRAPH_CHECKPOINT_URL must be a PostgreSQL connection URL"
        )

    connection_url = url.replace("postgresql+psycopg://", "postgresql://", 1)

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError:
        raise CheckpointUnavailable(
            "Durable workflow storage requires the "
            "langgraph-checkpoint-postgres package and a psycopg driver"
        ) from None

    try:
        import psycopg
        from psycopg.rows import dict_row

        connection = psycopg.connect(
            connection_url,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row,
            connect_timeout=10,
        )
        saver = PostgresSaver(connection)
        saver.setup()
    except Exception as exc:  # noqa: BLE001 - never surface credentials
        raise CheckpointUnavailable(
            "Durable workflow storage is unavailable "
            f"({type(exc).__name__})"
        ) from None

    return saver
