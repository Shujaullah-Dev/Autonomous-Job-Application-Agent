"""Adapters for the providers added beyond Greenhouse and Lever."""

import httpx
import pytest
from app.services.job_sources.arbeitnow import ArbeitnowSource
from app.services.job_sources.ashby import AshbySource
from app.services.job_sources.base import (
    JobSourceError,
    annual_salary,
    parse_datetime,
)
from app.services.job_sources.catalog import (
    SOURCES,
    default_sources,
)
from app.services.job_sources.himalayas import HimalayasSource
from app.services.job_sources.jobicy import JobicySource
from app.services.job_sources.remoteok import RemoteOkSource
from app.services.job_sources.remotive import RemotiveSource
from app.services.job_sources.smartrecruiters import (
    SmartRecruitersSource,
)
from app.services.job_sources.workable import WorkableSource


def client_for(handler) -> httpx.Client:
    return httpx.Client(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )


def test_ashby_normalization():
    def handler(request):
        assert "/job-board/demo" in str(request.url)

        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": "ashby-1",
                        "title": "Backend Engineer",
                        "location": "Berlin",
                        "employmentType": "FullTime",
                        "isListed": True,
                        "isRemote": False,
                        "workplaceType": "Hybrid",
                        "publishedAt": "2026-11-20T10:00:00.000+00:00",
                        "jobUrl": (
                            "https://jobs.ashbyhq.com/demo/ashby-1"
                        ),
                        "descriptionHtml": (
                            "<p>Build <strong>APIs</strong>.</p>"
                        ),
                    },
                    {
                        "id": "draft-1",
                        "title": "Hidden draft",
                        "isListed": False,
                        "jobUrl": (
                            "https://jobs.ashbyhq.com/demo/draft-1"
                        ),
                        "descriptionHtml": "<p>Secret</p>",
                    },
                ]
            },
        )

    with client_for(handler) as client:
        result = AshbySource(client).fetch(
            "demo",
            company_name="Demo Inc",
        )

    assert result.provider == "ashby"
    assert result.company_name == "Demo Inc"
    assert result.source_count == 2
    assert result.skipped_count == 1
    assert len(result.jobs) == 1

    job = result.jobs[0]

    assert job.title == "Backend Engineer"
    assert job.source == "ashby:demo"
    assert job.source_job_id == "ashby-1"
    assert job.work_mode == "hybrid"
    assert job.employment_type == "Full-time"
    assert job.description == "Build APIs."
    assert job.posted_at is not None


def test_ashby_rejects_invalid_board():
    with client_for(lambda request: httpx.Response(200, json={})) as client:
        with pytest.raises(JobSourceError) as exc:
            AshbySource(client).fetch("https://evil.example")

    assert exc.value.reason == "invalid_board_token"


def test_workable_normalization():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "name": "Demo Account",
                "jobs": [
                    {
                        "title": "Data Engineer",
                        "shortcode": "ABC123",
                        "url": "https://apply.workable.com/j/ABC123",
                        "published_on": "2026-11-19",
                        "telecommuting": True,
                        "employment_type": "Full-time",
                        "locations": [
                            {"city": "Paris", "country": "France"}
                        ],
                        "description": "<p>Own the pipelines.</p>",
                    }
                ],
            },
        )

    with client_for(handler) as client:
        result = WorkableSource(client).fetch("demo")

    assert result.company_name == "Demo Account"
    assert len(result.jobs) == 1

    job = result.jobs[0]

    assert job.source == "workable:demo"
    assert job.source_job_id == "ABC123"
    assert job.location == "Paris, France"
    assert job.work_mode == "remote"
    assert job.posted_at is not None


def test_smartrecruiters_reads_job_ad():
    def handler(request):
        if request.url.path.endswith("/postings"):
            return httpx.Response(
                200,
                json={
                    "totalFound": 1,
                    "content": [
                        {
                            "id": "7440001",
                            "name": "Site Reliability Engineer",
                            "company": {
                                "identifier": "demo",
                                "name": "Demo Group",
                            },
                            "releasedDate": "2026-11-18T09:00:00.000Z",
                            "location": {
                                "city": "Stuttgart",
                                "country": "de",
                                "fullLocation": "Stuttgart, Germany",
                                "remote": False,
                                "hybrid": True,
                            },
                            "typeOfEmployment": {"label": "Full-time"},
                        }
                    ],
                },
            )

        return httpx.Response(
            200,
            json={
                "jobAd": {
                    "sections": {
                        "companyDescription": {
                            "text": "<p>We build things.</p>"
                        },
                        "jobDescription": {
                            "text": "<p>Keep them running.</p>"
                        },
                    }
                }
            },
        )

    with client_for(handler) as client:
        result = SmartRecruitersSource(client).fetch("demo")

    assert len(result.jobs) == 1

    job = result.jobs[0]

    assert job.company_name == "Demo Group"
    assert job.source == "smartrecruiters:demo"
    assert job.location == "Stuttgart, Germany"
    assert job.work_mode == "hybrid"
    assert "We build things." in job.description
    assert "Keep them running." in job.description
    assert str(job.job_url) == (
        "https://jobs.smartrecruiters.com/demo/7440001"
    )


def test_remotive_normalization():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 2091179,
                        "url": (
                            "https://remotive.com/remote-jobs/"
                            "software-development/engineer-2091179"
                        ),
                        "title": "Platform Engineer",
                        "company_name": "Demo Remote",
                        "job_type": "full_time",
                        "publication_date": "2026-11-24T10:31:32",
                        "candidate_required_location": "Worldwide",
                        "description": "<p>Run the platform.</p>",
                    }
                ]
            },
        )

    with client_for(handler) as client:
        result = RemotiveSource(client).fetch()

    job = result.jobs[0]

    assert job.source == "remotive"
    assert job.source_job_id == "2091179"
    assert job.work_mode == "remote"
    assert job.location == "Worldwide"
    assert job.posted_at is not None


def test_arbeitnow_pages_until_short_page():
    def handler(request):
        assert request.url.params.get("page") == "1"

        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "slug": "demo-role",
                        "company_name": "Demo GmbH",
                        "title": "Werkstudent Data",
                        "description": (
                            "&lt;p&gt;Support the team.&lt;/p&gt;"
                        ),
                        "remote": False,
                        "url": (
                            "https://www.arbeitnow.com/jobs/"
                            "companies/demo/demo-role"
                        ),
                        "location": "Berlin",
                        "created_at": 1795622127,
                    }
                ]
            },
        )

    with client_for(handler) as client:
        result = ArbeitnowSource(client).fetch()

    job = result.jobs[0]

    assert job.source == "arbeitnow"
    assert job.description == "Support the team."
    assert job.location == "Berlin"
    assert job.posted_at is not None


def test_jobicy_keeps_annual_salary_only():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 164284,
                        "url": "https://jobicy.com/jobs/164284-engineer",
                        "jobTitle": "Remote Engineer",
                        "companyName": "Demo Labs",
                        "jobGeo": "USA",
                        "jobType": ["Full-Time"],
                        "jobDescription": "<p>Ship features.</p>",
                        "pubDate": "2026-11-25T13:24:25+00:00",
                        "salaryMin": 90000,
                        "salaryMax": 120000,
                        "salaryCurrency": "USD",
                        "salaryPeriod": "yearly",
                    }
                ]
            },
        )

    with client_for(handler) as client:
        result = JobicySource(client).fetch()

    job = result.jobs[0]

    assert job.salary_min == 90000
    assert job.salary_max == 120000
    assert job.salary_currency == "USD"
    assert job.work_mode == "remote"


def test_remoteok_skips_terms_entry():
    def handler(request):
        return httpx.Response(
            200,
            json=[
                {"legal": "Remote OK API terms"},
                {
                    "id": "1138100",
                    "position": "Senior Engineer",
                    "company": "Demo Remote OK",
                    "location": "Worldwide",
                    "date": "2026-11-24T11:40:05+00:00",
                    "url": (
                        "https://remoteok.com/remote-jobs/"
                        "senior-engineer-1138100"
                    ),
                    "description": "<p>Own the stack.</p>",
                    "tags": ["python"],
                    "salary_min": 0,
                    "salary_max": 0,
                },
            ],
        )

    with client_for(handler) as client:
        result = RemoteOkSource(client).fetch()

    assert result.source_count == 2
    assert len(result.jobs) == 1

    job = result.jobs[0]

    assert job.source == "remoteok"
    assert job.salary_min is None
    assert job.salary_currency is None
    assert "Tags: python" in job.description


def test_himalayas_uses_application_link():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "title": "Staff Engineer",
                        "companyName": "Demo Himalayas",
                        "employmentType": "Full Time",
                        "minSalary": "120000",
                        "maxSalary": "160000",
                        "currency": "USD",
                        "salaryPeriod": "annual",
                        "locationRestrictions": [
                            "United States",
                            "Canada",
                        ],
                        "description": "<p>Lead the team.</p>",
                        "pubDate": 1795611998,
                        "guid": (
                            "https://himalayas.app/companies/demo/"
                            "jobs/staff-engineer"
                        ),
                        "applicationLink": (
                            "https://himalayas.app/companies/demo/"
                            "jobs/staff-engineer"
                        ),
                    }
                ]
            },
        )

    with client_for(handler) as client:
        result = HimalayasSource(client).fetch()

    job = result.jobs[0]

    assert job.source == "himalayas"
    assert job.location == "United States, Canada"
    assert job.salary_min == 120000
    assert job.work_mode == "remote"
    assert job.posted_at is not None


def test_annual_salary_rejects_hourly_and_unknown_currency():
    assert annual_salary(20, 30, "USD", "hourly") == (
        None,
        None,
        None,
    )
    assert annual_salary(20, 30, "dollars", "annual") == (
        None,
        None,
        None,
    )
    assert annual_salary(0, 0, "USD", "annual") == (
        None,
        None,
        None,
    )
    assert annual_salary("90000", 80000, "eur", "annual") == (
        80000,
        90000,
        "EUR",
    )


def test_parse_datetime_handles_unix_and_iso():
    assert parse_datetime(1795611998) is not None
    assert parse_datetime("1795611998") is not None
    assert parse_datetime("2026-11-24T10:31:32") is not None
    assert parse_datetime("not-a-date") is None
    assert parse_datetime(None) is None


def test_default_catalog_only_uses_supported_providers():
    specs = default_sources()

    assert specs
    assert {spec.provider for spec in specs} <= set(SOURCES)

    keys = [
        (spec.provider, spec.identifier.casefold())
        for spec in specs
    ]

    assert len(keys) == len(set(keys))

    assert {
        "greenhouse",
        "lever",
        "ashby",
        "workable",
        "smartrecruiters",
        "remotive",
        "arbeitnow",
        "jobicy",
        "remoteok",
        "himalayas",
    } <= {spec.provider for spec in specs}
