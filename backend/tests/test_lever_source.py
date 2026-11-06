
import httpx
import pytest
from app.services.job_sources.greenhouse import (
    JobSourceError,
)
from app.services.job_sources.lever import (
    LeverSource,
)


def lever_handler(request):
    if request.url.params.get("mode") != "json":
        return httpx.Response(400)

    return httpx.Response(
        200,
        json=[
            {
                "id": "lever-job-101",
                "text": "Python Developer",
                "categories": {
                    "location": "Remote",
                    "commitment": "Full-time",
                    "team": "Engineering",
                },
                "descriptionPlain": (
                    "Build APIs using Python and FastAPI."
                ),
                "hostedUrl": (
                    "https://jobs.lever.co/demo/101"
                ),
                "applyUrl": (
                    "https://jobs.lever.co/demo/101/apply"
                ),
                "workplaceType": "remote",
            }
        ],
    )


def test_lever_normalization():
    with httpx.Client(
        transport=httpx.MockTransport(
            lever_handler
        )
    ) as client:

        result = LeverSource(client).fetch(
            "demo",
            company_name="Demo Technologies",
        )

    assert result.provider == "lever"
    assert result.account_identifier == "demo"
    assert len(result.jobs) == 1

    job = result.jobs[0]

    assert job.title == "Python Developer"
    assert job.company_name == "Demo Technologies"
    assert job.location == "Remote"
    assert job.source == "lever:demo"
    assert job.source_job_id == "lever-job-101"
    assert job.work_mode == "remote"
    assert job.employment_type == "Full-time"


def test_missing_company_name():
    with httpx.Client(
        transport=httpx.MockTransport(
            lever_handler
        )
    ) as client:

        with pytest.raises(JobSourceError) as exc:
            LeverSource(client).fetch("demo")

    assert exc.value.reason == "company_name_required"


def test_invalid_site():
    with httpx.Client(
        transport=httpx.MockTransport(
            lever_handler
        )
    ) as client:

        with pytest.raises(JobSourceError) as exc:
            LeverSource(client).fetch(
                "https://evil.com"
            )

    assert exc.value.reason == "invalid_site_identifier"


def test_lever_rate_limit():
    def handler(request):
        return httpx.Response(429)

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:

        with pytest.raises(JobSourceError) as exc:
            LeverSource(client).fetch(
                "demo",
                company_name="Demo",
            )

    assert exc.value.reason == "rate_limited"


def test_lever_invalid_json():
    def handler(request):
        return httpx.Response(
            200,
            text="not-json",
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:

        with pytest.raises(JobSourceError) as exc:
            LeverSource(client).fetch(
                "demo",
                company_name="Demo",
            )

    assert exc.value.reason == "invalid_json"
