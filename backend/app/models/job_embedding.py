
"""Job embedding metadata and Supabase pgvector column."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import UserDefinedType

from app.db.base import Base


class SupabaseVector(UserDefinedType):
    """A 384-dimensional vector stored in the extensions schema."""

    cache_ok = True

    def get_col_spec(self, **kw):
        return "extensions.vector(384)"


@compiles(SupabaseVector, "sqlite")
def _sqlite_vector_type(element, compiler, **kw):
    """Allow existing SQLite unit tests to create metadata."""
    return "TEXT"


class JobEmbedding(Base):
    __tablename__ = "job_embeddings"

    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )

    model_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    embedding: Mapped[str] = mapped_column(
        SupabaseVector(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
