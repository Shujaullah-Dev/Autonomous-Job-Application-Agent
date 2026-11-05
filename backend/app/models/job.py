
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    Text,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"

    __table_args__ = (
        CheckConstraint(
            "salary_min IS NULL OR salary_min >= 0",
            name="ck_jobs_salary_min_nonnegative",
        ),
        CheckConstraint(
            "salary_max IS NULL OR salary_max >= 0",
            name="ck_jobs_salary_max_nonnegative",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL "
            "OR salary_max >= salary_min",
            name="ck_jobs_salary_range",
        ),
        CheckConstraint(
            "work_mode IS NULL OR work_mode "
            "IN ('remote', 'hybrid', 'onsite')",
            name="ck_jobs_work_mode",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    company_name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True
    )

    location: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )

    description: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    job_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, unique=True
    )

    source: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    employment_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )

    work_mode: Mapped[str | None] = mapped_column(
        String(16), nullable=True, index=True
    )

    salary_min: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    salary_max: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    salary_currency: Mapped[str | None] = mapped_column(
        String(3), nullable=True
    )

    posted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # <-- Ensure this exists
    employment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
