# AI Job Agent

AI Job Agent is an early-stage FastAPI backend for maintaining candidate profiles, reviewing structured information extracted from resumes, and importing jobs from supported providers.

## What is implemented

- Health checks and candidate profile create, read, and partial update endpoints.
- Candidate skill, work experience, and education management.
- PDF and DOCX resume preview, with a local parser and optional Groq-powered extraction.
- A separate, explicitly approved resume-import endpoint that adds reviewed details and skips duplicates.
- Multi-source job discovery and ingestion from Greenhouse Job Board and Lever Postings APIs, with dry-run and apply modes.
- SQLAlchemy models and Alembic migrations for candidate profiles, skills, experience, education, and jobs. **The migration history needs repair before it can reliably provision a fresh database.**

There is no authentication or authorization. Do not expose this API to untrusted networks or use it with real candidate data in a shared environment.

## Project layout

```text
backend/
  app/
    api/routes/       API endpoints
    core/             Environment-backed settings
    db/               SQLAlchemy base and sessions
    models/            Database models
    schemas/           Request and response validation
    services/          Resume processing, job-source adapters, and ingestion
    scripts/           Job ingestion command-line tools
    main.py            FastAPI application
  alembic/             Database migration environment and revisions
  tests/               Backend tests
docs/
  architecture.md      Current design and future boundaries
  roadmap.md           Implemented features and next steps
  technical-stack.md   Dependencies and configuration
```

## Setup

Requirements: Python 3.10.2 or newer, pip, and a PostgreSQL database.

In PowerShell from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` in `.env` to your database connection URL. This setting is required when the application starts. Keep credentials private and never commit `.env`.

The app does not create database tables at startup. **Do not run Alembic against a fresh or important database until the migration chain has been repaired and tested.** See [Database migrations](#database-migrations).

Start the API from the repository root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## API overview

All profile endpoints use `/api/v1/candidates`. FastAPI provides request validation and interactive documentation at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check that the API responds |
| `GET` | `/health/db` | Check database connectivity |
| `POST` | `/api/v1/candidates` | Create a candidate profile |
| `GET` | `/api/v1/candidates/{candidate_id}` | Get a profile by UUID |
| `PATCH` | `/api/v1/candidates/{candidate_id}` | Partially update a profile |
| `POST` | `/api/v1/candidates/{candidate_id}/skills` | Add a skill |
| `GET` | `/api/v1/candidates/{candidate_id}/skills` | List skills |
| `PATCH` | `/api/v1/candidates/{candidate_id}/skills/{skill_id}` | Update a skill |
| `DELETE` | `/api/v1/candidates/{candidate_id}/skills/{skill_id}` | Delete a skill |
| `POST` | `/api/v1/candidates/{candidate_id}/experiences` | Add work experience |
| `GET` | `/api/v1/candidates/{candidate_id}/experiences` | List work experience |
| `PATCH` | `/api/v1/candidates/{candidate_id}/experiences/{experience_id}` | Update work experience |
| `DELETE` | `/api/v1/candidates/{candidate_id}/experiences/{experience_id}` | Delete work experience |
| `POST` | `/api/v1/candidates/{candidate_id}/education` | Add education |
| `GET` | `/api/v1/candidates/{candidate_id}/education` | List education |
| `PATCH` | `/api/v1/candidates/{candidate_id}/education/{education_id}` | Update education |
| `DELETE` | `/api/v1/candidates/{candidate_id}/education/{education_id}` | Delete education |
| `POST` | `/api/v1/candidates/{candidate_id}/resume/preview` | Analyze an uploaded resume without saving it |
| `POST` | `/api/v1/candidates/{candidate_id}/resume/import` | Import reviewed, explicitly approved records |

Most create operations return `201`; delete operations return `204`. Missing candidates or child records return `404`. Invalid input generally returns `422`; empty partial updates return `400`; duplicate conflicts may return `409`. See `/docs` for the detailed request and response schemas.

### Resume review and import

Upload a PDF or DOCX as multipart form data in the `file` field to the preview endpoint. Files must be at most 5 MiB and have a matching filename extension and content type. Password-protected PDFs and files with no extractable text are not supported. The endpoint returns extracted contact details, skills, experience, education, parser information, and warnings; it does not store the file or modify the candidate profile.

By default, the local parser is used. It recognizes a fixed skill catalog and common resume section layouts, so results may be incomplete. Optional Groq extraction can be enabled with `RESUME_AI_ENABLED=true` and a `GROQ_API_KEY`; in that mode, extracted resume text is sent to Groq. The service validates returned fields against source text and falls back to local parsing when Groq is unavailable. Review all results before importing.

Send selected records to the import endpoint as JSON with `"approved": true`. The import API rejects unapproved requests, requires at least one selected record, and reports created and skipped counts. It avoids duplicate skills and duplicate experience or education records. Preview and import are separate requests: the import endpoint accepts reviewed data; it does not itself verify that the supplied details came from a prior preview.

## Multi-Source Job Discovery

The job importer supports the Greenhouse Job Board API and Lever Postings API. Provider adapters normalize their listings into the shared job schema. Each imported listing retains its provider (`source`) and provider-specific identifier (`source_job_id`), along with its original `job_url` and normalized `canonical_url`.

The ingestion pipeline canonicalizes URLs and checks existing jobs by provider identity and canonical URL. It also checks company/title/location fingerprints for likely cross-provider duplicates; possible duplicates are skipped and reported. Both providers use the same `jobs` table, which can be hosted on PostgreSQL or Supabase.

The importer defaults to a dry run and does not commit database changes unless `--apply` is passed. From the `backend` directory, for example:

```powershell
python -m app.scripts.ingest_jobs --greenhouse-board example-board
python -m app.scripts.ingest_jobs --lever-site example-site --lever-company-name "Example Company"
python -m app.scripts.ingest_jobs --greenhouse-board example-board --lever-site example-site --lever-company-name "Example Company" --apply
```

Repeat `--greenhouse-board` or `--lever-site` to import from multiple accounts. Each `--lever-site` must have a corresponding `--lever-company-name` in the same order. The command uses `DATABASE_URL` from the repository-root `.env`. Review the dry-run summary before applying imports.

## Database migrations

The ORM defines `candidate_profiles`, `candidate_skills`, `work_experiences`, `educations`, and `jobs`. Jobs are ingested through the command-line importer; there is no public job ingestion API.

Alembic is configured in `alembic.ini` and loads its URL from `DATABASE_URL`. Two consecutive revisions, `fa05578eada4` and `5b0bd740df7a`, both create `candidate_profiles`; therefore, upgrading a clean database to head is expected to fail. The candidate migration columns and constraints also do not fully match the model. Repair and test the migration history before using it to create or update a database. Inspect generated migrations and back up important data before applying schema changes.

## Development checks

Run tests and lint from the repository root:

```powershell
python -m pytest
python -m ruff check .
```

Tests cover health checks, model and schema behavior, resume validation/parsing/analysis, Groq fallback behavior, and reviewed resume import. Database migrations and candidate persistence against a production database are not comprehensively integration-tested.

## Future work

Job search, matching, AI-generated application materials, application tracking, authentication, a frontend, notifications, and deployment infrastructure remain future work. Job-source requests should respect provider terms and access controls; consequential actions should require user approval.

## Documentation

- [Architecture](docs/architecture.md) — implemented components and target design.
- [Roadmap](docs/roadmap.md) — current status and suggested priorities.
- [Technical stack](docs/technical-stack.md) — dependencies, settings, and persistence.
