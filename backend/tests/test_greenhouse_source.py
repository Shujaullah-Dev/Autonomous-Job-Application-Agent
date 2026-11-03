
import httpx
import pytest
from app.services.job_sources.greenhouse import (
    GreenhouseSource,
    JobSourceError,
    html_to_text,
)


def mock_greenhouse(request: httpx.Request):
    if request.url.path == "/v1/boards/demo":
        return httpx.Response(
            200,
            json={"name": "Demo Technologies"},
        )

    if request.url.path == "/v1/boards/demo/jobs":
        assert request.url.params["content"] == "true"

        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 101,
                        "internal_job_id": 501,
                        "title": "Python Developer",
                        "absolute_url": (
                            "https://example.com/jobs/101"
                        ),
                        "location": {
                            "name": "Remote"
                        },
                        "content": (
                            "<p>Python &amp; FastAPI</p>"
                        ),
                    },
                    {
                        "id": 102,
                        "internal_job_id": None,
                        "title": "Prospective Candidate",
                        "absolute_url": (
                            "https://example.com/jobs/102"
                        ),
                        "content": "<p>Talent pool</p>",
                    },
                ]
            },
        )

    return httpx.Response(404)


def test_fetch_and_normalize():
    transport = httpx.MockTransport(
        mock_greenhouse
    )

    with httpx.Client(transport=transport) as client:
        result = GreenhouseSource(client).fetch(
            "demo"
        )

    assert result.company_name == "Demo Technologies"
    assert result.source_count == 2
    assert result.skipped_count == 1
    assert len(result.jobs) == 1

    job = result.jobs[0]

    assert job.title == "Python Developer"
    assert job.source == "greenhouse:demo"
    assert job.work_mode == "remote"
    assert job.description == "Python & FastAPI"
    assert job.salary_min is None
    assert job.posted_at is None


def test_invalid_board_token():
    transport = httpx.MockTransport(
        mock_greenhouse
    )

    with httpx.Client(transport=transport) as client:
        with pytest.raises(JobSourceError) as exc:
            GreenhouseSource(client).fetch(
                "https://example.com"
            )

    assert exc.value.reason == "invalid_board_token"


def test_rate_limit():
    def handler(request):
        return httpx.Response(429)

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(JobSourceError) as exc:
            GreenhouseSource(client).fetch("demo")

    assert exc.value.reason == "rate_limited"
    assert exc.value.status_code == 429


def test_board_not_found():
    def handler(request):
        return httpx.Response(404)

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(JobSourceError) as exc:
            GreenhouseSource(client).fetch(
                "nonexistent-board"
            )

    assert exc.value.reason == "board_not_found"


def test_network_timeout():
    def handler(request):
        raise httpx.ConnectTimeout(
            "Simulated timeout"
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(JobSourceError) as exc:
            GreenhouseSource(client).fetch("demo")

    assert exc.value.reason == "timeout"


def test_html_description_conversion():
    text = html_to_text(
        "<p>Build <strong>APIs</strong></p>"
        "<script>alert('test')</script>"
    )

    assert text == "Build APIs"
    assert "alert" not in text
