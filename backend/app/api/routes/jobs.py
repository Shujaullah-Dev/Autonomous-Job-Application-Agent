
import secrets
from typing import Annotated

from app.core.config import settings
from app.db.session import get_db
from app.models.job import Job
from app.schemas.job import (
    JobCreate,
    JobListResponse,
    JobRead,
    WorkMode,
)
from app.services.job_search import search_jobs
from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

router = APIRouter(
    prefix="/api/v1/jobs",
    tags=["Jobs"],
)


def require_dev_write_key(
    provided_key: Annotated[
        str | None,
        Header(alias="X-Dev-Job-Key"),
    ] = None,
) -> None:
    """Allow job creation only in configured development mode."""

    if settings.app_env.lower() != "development":
        raise HTTPException(
            status_code=403,
            detail="Job writes are disabled outside development",
        )

    if not settings.dev_job_write_key:
        raise HTTPException(
            status_code=503,
            detail="DEV_JOB_WRITE_KEY is not configured",
        )

    if not provided_key or not secrets.compare_digest(
        provided_key, settings.dev_job_write_key
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid development job write key",
        )


@router.get(
    "",
    response_model=JobListResponse,
)
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[
        str | None, Query(max_length=100)
    ] = None,
    company: Annotated[
        str | None, Query(max_length=255)
    ] = None,
    location: Annotated[
        str | None, Query(max_length=255)
    ] = None,
    work_mode: WorkMode | None = None,
    employment_type: Annotated[
        str | None, Query(max_length=50)
    ] = None,
    minimum_salary: Annotated[
        int | None, Query(ge=0)
    ] = None,
    salary_currency: Annotated[
        str | None, Query(pattern=r"^[A-Za-z]{3}$")
    ] = None,
    limit: Annotated[
        int, Query(ge=1, le=100)
    ] = 20,
    offset: Annotated[
        int, Query(ge=0)
    ] = 0,
) -> JobListResponse:
    if minimum_salary is not None and not salary_currency:
        raise HTTPException(
            status_code=422,
            detail=(
                "salary_currency is required "
                "with minimum_salary"
            ),
        )

    total, items = search_jobs(
        db=db,
        q=q,
        company=company,
        location=location,
        work_mode=work_mode,
        employment_type=employment_type,
        minimum_salary=minimum_salary,
        salary_currency=salary_currency,
        limit=limit,
        offset=offset,
    )

    return JobListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get(
    "/{job_id}",
    response_model=JobRead,
)
def get_job(
    job_id: Annotated[int, Path(ge=1)],
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    job = db.get(Job, job_id)

    if job is None or not job.is_active:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    return job


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_dev_write_key)],
)
def create_job(
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
) -> Job:
    job = Job(**payload.model_dump(mode="json"))
    db.add(job)

    try:
        db.commit()
        db.refresh(job)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "Job URL already exists or data conflicts "
                "with a database constraint"
            ),
        ) from None

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Could not save the job",
        ) from None

    return job