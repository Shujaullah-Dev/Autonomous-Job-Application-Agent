# AI Job Agent

AI Job Agent is an early-stage backend foundation for an AI-assisted job-search and application-management tool. The long-term goal is to help a candidate organize their profile, discover relevant jobs, prepare application materials, and track applications while keeping consequential actions under the user's control.

> **Current state:** The repository currently contains a FastAPI backend with health checks, candidate-profile create/read/update endpoints, SQLAlchemy models for candidate profiles and jobs, and Alembic migrations. Resume processing, job ingestion and search, matching, AI generation, application tracking, a frontend, and deployment services are not implemented yet. See [the roadmap](docs/roadmap.md) for a feature-by-feature status.

## Contents

- [What works today](#what-works-today)
- [Repository structure](#repository-structure)
- [How the backend works](#how-the-backend-works)
- [Getting started](#getting-started)
- [API reference](#api-reference)
- [Database and migrations](#database-and-migrations)
- [Tests and linting](#tests-and-linting)
- [Planned workflow](#planned-workflow)
- [Project documentation](#project-documentation)

## What works today

| Area | Current implementation |
| --- | --- |
| API | FastAPI application in `backend/app/main.py` |
| Health | `GET /health` and database connectivity check `GET /health/db` |
| Candidate profiles | Create, fetch by UUID, and partially update a profile |
| Database access | SQLAlchemy 2.x engine and request-scoped sessions |
| Data models | Candidate profile and job SQLAlchemy models |
| Input/output validation | Pydantic candidate request and response schemas |
| Schema migrations | Alembic is configured; the candidate-profile migration history currently contains a duplicate table-creation revision (see [Database and migrations](#database-and-migrations)) |
| Automated checks | pytest tests for health endpoints and job model metadata |

There is currently no frontend or implemented resume, job-search, matching, LLM, application, notification, or calendar workflow. The architecture and stack documents describe those as future work, not existing capabilities.

## Repository structure

```text
.
├── backend/
│   ├── alembic/
│   │   ├── env.py                 # Loads settings and SQLAlchemy model metadata
│   │   └── versions/              # Versioned database schema changes
│   ├── app/
│   │   ├── api/routes/
│   │   │   └── candidates.py      # Candidate-profile endpoints
│   │   ├── core/
│   │   │   └── config.py          # Environment-backed application settings
│   │   ├── db/
│   │   │   ├── base.py            # SQLAlchemy declarative base
│   │   │   └── session.py         # Engine, session factory, DB dependency
│   │   ├── models/
│   │   │   ├── candidate.py       # CandidateProfile table model
│   │   │   └── job.py             # Job table model
│   │   ├── schemas/
│   │   │   └── candidate.py       # Candidate request/response validation
│   │   └── main.py                # FastAPI app, routers, health checks
│   ├── tests/
│   │   ├── test_health.py
│   │   └── test_job_model.py
│   └── requirements.txt           # Backend dependency list
├── docs/
│   ├── architecture.md            # Implemented architecture and target design
│   ├── roadmap.md                 # Current progress and next steps
│   └── technical-stack.md         # Dependencies in use and planned technology
├── .env.example                   # Configuration template (no real credentials)
├── alembic.ini                    # Alembic entry-point configuration
├── pyproject.toml                 # Project metadata, pytest, Ruff configuration
└── requirements.txt               # Root Python dependency list
```

## How the backend works

1. `app.main` creates the FastAPI application using the configured app name and debug flag.
2. The candidate router is mounted at `/api/v1/candidates`.
3. Candidate endpoints receive a SQLAlchemy `Session` through the `get_db` dependency. The dependency opens a session for the request and closes it afterward.
4. Pydantic schemas validate incoming candidate data and shape API responses.
5. SQLAlchemy models map candidate profiles and jobs to database tables. Alembic is intended to manage the schema separately from application startup.

See [architecture.md](docs/architecture.md) for the implemented component boundaries and the proposed end-to-end product architecture.

## Getting started

### Requirements

- Python 3.10.2 or later
- pip
- A PostgreSQL database and a SQLAlchemy-compatible PostgreSQL connection URL

No Docker Compose configuration is currently present. The API does not create tables automatically at startup.

### Create an environment and install dependencies

From the repository root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The root requirements file is the default installation manifest. `backend/requirements.txt` adds a `psycopg` dependency to the root list.

### Configure the database

Copy the template and edit `.env`:

```powershell
Copy-Item .env.example .env
```

Set `DATABASE_URL` to the connection URL for a database available to your machine. The current settings class requires this value; the application cannot initialize without it. Do not commit `.env` or put credentials in documentation. The template includes additional settings for future services, but the current application only reads `APP_NAME`, `APP_ENV`, `DEBUG`, `API_HOST`, `API_PORT`, and `DATABASE_URL`. `APP_ENV`, `API_HOST`, and `API_PORT` are loaded but do not currently change behavior in the application code.

### Start the API

From the repository root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

When running, open `http://127.0.0.1:8000/docs` for FastAPI's interactive API documentation. The API process requires a usable `DATABASE_URL` at startup even when calling only the non-database health endpoint.

## API reference

### Health checks

| Method and path | Purpose | Success response |
| --- | --- | --- |
| `GET /health` | Confirms the API process responds | `{"status":"ok"}` |
| `GET /health/db` | Executes `SELECT 1` against the configured database | `{"status":"ok","database":"connected"}` |

The database health endpoint returns HTTP 503 when the database operation raises a SQLAlchemy error.

### Candidate profiles

All candidate routes use the `/api/v1/candidates` prefix.

| Method and path | Purpose | Responses of note |
| --- | --- | --- |
| `POST /api/v1/candidates` | Create a candidate profile | 201 on success; 409 if a database integrity constraint fails; 422 for invalid input |
| `GET /api/v1/candidates/{candidate_id}` | Fetch one profile by UUID | 404 if not found |
| `PATCH /api/v1/candidates/{candidate_id}` | Update supplied fields | 404 if not found; 400 if the body has no fields; 409 if a database integrity constraint fails; 422 for invalid input |

`CandidateCreate` requires `full_name` and `email`. The name is trimmed and cannot be blank; email is validated; optional fields include phone, location, professional summary, and years of experience (0–80). `CandidateUpdate` accepts those fields as optional values. A successful response includes the UUID and creation/update timestamps.

Example create request:

```json
{
  "full_name": "Taylor Example",
  "email": "taylor@example.com",
  "location": "Toronto",
  "years_experience": 5
}
```

This API currently has no authentication or authorization. Do not expose it to untrusted networks with real candidate data.

## Database and migrations

The database layer uses SQLAlchemy 2.x and Alembic. The models currently describe:

- `candidate_profiles`: UUID primary key, name, unique/indexed email, optional contact/profile fields, and creation/update timestamps.
- `jobs`: integer primary key, title, company, optional location/source/employment type, description, unique job URL, and timestamps. There are no job API routes yet.

Alembic configuration is at the repository root and points to `backend/alembic`. Migration settings read `DATABASE_URL` through the same application settings as the API.

> **Migration issue:** Both `fa05578eada4_create_candidate_profiles.py` and `5b0bd740df7a_create_candidate_profiles_table.py` create a `candidate_profiles` table. They are consecutive revisions after the jobs migration, so a fresh `alembic upgrade head` is expected to fail when the second revision attempts to create the already-existing table. The candidate migrations also do not fully match the current model constraints. Treat migrations as needing repair before relying on them to provision a fresh database.

Once the migration history has been corrected, the intended commands from the repository root are:

```powershell
$env:PYTHONPATH = "backend"
python -m alembic upgrade head
python -m alembic revision --autogenerate -m "describe schema change"
```

The Alembic environment imports the `app` package from `backend`, so make that directory importable when running Alembic from the repository root.

Always inspect and test generated migrations before applying them to a database with important data.

## Tests and linting

Run tests from the repository root:

```powershell
python -m pytest
```

Run Ruff:

```powershell
python -m ruff check .
```

Pytest is configured to discover tests under `backend/tests` and add `backend` to the import path. Existing tests cover health endpoint behavior (with a mocked database session) and job model metadata. They do not test candidate CRUD against a real database or the Alembic migration chain.

## Planned workflow

The product goal is to progress toward this user-controlled workflow:

```text
Candidate profile / resume
          ↓
Permitted job discovery
          ↓
Normalization and deduplication
          ↓
Explainable job matching
          ↓
Draft application materials
          ↓
User review and explicit approval
          ↓
Permitted application workflow
          ↓
Application, interview, and deadline tracking
```

Only candidate profile storage and the initial job table model exist today. The rest of the flow is planned; consult [roadmap.md](docs/roadmap.md) for current status and priorities. Any future automation must respect source terms, access controls, rate limits, and user approval for consequential actions.

## Project documentation

- [Architecture](docs/architecture.md) — what is implemented now and the target design
- [Roadmap](docs/roadmap.md) — progress, gaps, and recommended implementation order
- [Technical stack](docs/technical-stack.md) — actual dependencies versus proposed choices
