from app.db.base import Base
from app.models.job import Job


def test_job_table_registered():
    assert "jobs" in Base.metadata.tables


def test_job_columns():
    columns = Base.metadata.tables["jobs"].columns

    expected_columns = {
        "id",
        "title",
        "company_name",
        "location",
        "description",
        "job_url",
        "source",
        "employment_type",
        "created_at",
        "updated_at",
    }

    assert expected_columns.issubset(set(columns.keys()))


def test_job_primary_key():
    primary_key_columns = {column.name for column in Job.__table__.primary_key.columns}

    assert primary_key_columns == {"id"}


def test_job_url_is_unique():
    job_url_column = Job.__table__.columns["job_url"]

    assert job_url_column.unique is True
