
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.job import Job


def escape_like(text: str) -> str:
    """Treat SQL LIKE wildcard characters as literal input."""
    return (
        text.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def search_jobs(
    db: Session,
    *,
    q: str | None = None,
    company: str | None = None,
    location: str | None = None,
    work_mode: str | None = None,
    employment_type: str | None = None,
    minimum_salary: int | None = None,
    salary_currency: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[Job]]:
    """Return total matching jobs and the requested result page."""

    query = select(Job).where(Job.is_active.is_(True))

    # Keyword search
    if q and q.strip():
        pattern = f"%{escape_like(q.strip())}%"

        query = query.where(
            or_(
                Job.title.ilike(pattern, escape="\\"),
                Job.company_name.ilike(pattern, escape="\\"),
                Job.description.ilike(pattern, escape="\\"),
            )
        )

    # Company filter
    if company and company.strip():
        pattern = f"%{escape_like(company.strip())}%"
        query = query.where(
            Job.company_name.ilike(pattern, escape="\\")
        )

    # Location filter
    if location and location.strip():
        pattern = f"%{escape_like(location.strip())}%"
        query = query.where(
            Job.location.ilike(pattern, escape="\\")
        )

    # Remote, hybrid, onsite
    if work_mode:
        query = query.where(Job.work_mode == work_mode)

    # Employment type
    if employment_type:
        query = query.where(
            func.lower(Job.employment_type)
            == employment_type.lower()
        )

    # Currency must be filtered before comparing salaries
    if salary_currency:
        query = query.where(
            Job.salary_currency == salary_currency.upper()
        )

    if minimum_salary is not None:
        query = query.where(
            func.coalesce(
                Job.salary_max, Job.salary_min
            ) >= minimum_salary
        )

    # Count all matching records before pagination
    total = db.scalar(
        select(func.count()).select_from(query.subquery())
    ) or 0

    # Stable ordering and pagination
    paginated_query = (
        query.order_by(
            Job.created_at.desc(),
            Job.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    items = list(db.scalars(paginated_query).all())

    return total, items