# AI Job Agent

AI Job Agent pairs a FastAPI backend with a React frontend. The backend maintains candidate profiles, reviews structured information extracted from resumes, imports jobs from supported providers, and exposes application-tracking, follow-up, interview, and notification routes. The frontend provides a complete sample journey, a live job search, and an optional Supabase account flow.

## What is implemented

- Health checks and candidate profile create, read, and partial update endpoints.
- Candidate skill, work experience, and education management.
- PDF and DOCX resume preview, with a local parser and optional Groq-powered extraction.
- A separate, explicitly approved resume-import endpoint that adds reviewed details and skips duplicates.
- Multi-source job discovery and ingestion from Greenhouse, Lever, Ashby, Workable and SmartRecruiters public APIs plus the Remotive, Arbeitnow, Jobicy, Remote OK and Himalayas feeds, with dry-run, apply and a curated `--defaults` set.
- Job search and detail routes with keyword, company, location, work mode, employment type, and salary filters.
- Workflow, application draft, manual handoff, follow-up, interview, and notification routes. They require a verified Supabase access token and candidate ownership; the development key remains available for local development.
- A React frontend with onboarding, profile, resume review, job search, shortlists, applications, follow-ups, interviews, notifications, and settings screens, plus desktop and mobile browser tests.
- An explicit CORS allowlist for the local frontend origins.
- SQLAlchemy models and Alembic migrations for candidate profiles, skills, experience, education, and jobs. **The migration history needs repair before it can reliably provision a fresh database.**

Security status: the API verifies Supabase access tokens and scopes every candidate-scoped route to the token subject (`backend/app/core/auth.py`, `candidate_profiles.owner_id`). Identity verification is active only when `SUPABASE_URL` or the JWKS settings are configured. The signed-in workspace now reads and writes those routes; the sample workspace remains an explicit opt-in. The migration history still needs repair and workflow checkpoints are durable only with `LANGGRAPH_CHECKPOINT_URL`. Keep the API on loopback or a private network and use synthetic data until the remaining gates in [docs/production-readiness.md](docs/production-readiness.md) are closed.

## Project layout

```text
backend/
  app/
    api/routes/       API endpoints
    core/             Environment-backed settings
    db/               SQLAlchemy base and sessions
    models/            Database models
    schemas/           Request and response validation
    services/          Resume processing, job-source adapters, ingestion, matching, workflows
    scripts/           Job ingestion and deployment smoke tools
    main.py            FastAPI application
  alembic/             Database migration environment and revisions
  tests/               Backend tests
frontend/
  src/app/             Router, providers, demo store
  src/pages/           Feature screens
  src/lib/             API client, generated types, demo fixtures, calendar export
  e2e/                 Playwright desktop and mobile journeys
  scripts/             OpenAPI export and screenshot helpers
docs/
  architecture.md      Job discovery design
  roadmap.md           Implemented features and next steps
  technical-stack.md   Dependencies and configuration
  frontend.md          Frontend handover, routes, and integration boundaries
  testing.md           Local QA and desktop/mobile test plan
  ci-cd.md             GitHub Actions workflows
```

## Setup

Requirements: Python 3.10.2 or newer, pip, Node 24 with npm, and a database. PostgreSQL is the production target; a throwaway SQLite file is enough for local QA.

In PowerShell from the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` and `DEV_JOB_WRITE_KEY` in `.env`. Both are required when the application starts. Keep credentials private and never commit `.env`.

The app does not create database tables at startup. **Do not run Alembic against a fresh or important database until the migration chain has been repaired and tested.** See [Database migrations](#database-migrations) and [Local QA and device testing](docs/testing.md#2-create-a-disposable-local-database) for the SQLite QA alternative.

Start the API from the repository root:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

Start the frontend in a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Choose **Explore the demo** for a complete sample journey that needs no backend or account. Live job search and profile writes call the API.

## Environment variables

The backend reads only the repository-root `.env`. The frontend reads only `frontend/.env.local`; it does not read the root `.env`.

### Backend

| Variable | Default | Effect |
| --- | --- | --- |
| `DATABASE_URL` | Required | SQLAlchemy connection URL; the API fails to start without it |
| `DEV_JOB_WRITE_KEY` | Required | Development-only key for job creation and the private feature routers; required at startup |
| `SUPABASE_URL` | Empty | Supabase project URL; derives the token JWKS URL and expected issuer |
| `SUPABASE_JWT_SECRET` | Empty | Legacy symmetric JWT secret for HS256 access tokens |
| `SUPABASE_JWKS_URL` | Empty | Explicit JWKS URL when `SUPABASE_URL` is not set |
| `SUPABASE_JWT_ISSUER` | Empty | Expected `iss` claim for access tokens |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected `aud` claim |
| `LANGGRAPH_CHECKPOINT_URL` | Empty | PostgreSQL URL for durable workflow checkpoints; unset keeps the in-process saver |
| `APP_ENV` | `development` | Key-gated writes return `403` when this is not `development` |
| `FRONTEND_URL` | `http://localhost:3000` | First CORS origin; must match the browser origin exactly |
| `DEBUG` | `false` | FastAPI debug mode |
| `API_HOST`, `API_PORT` | `127.0.0.1`, `8000` | Loaded settings; the Uvicorn command sets the actual bind |
| `JOB_SOURCE_TIMEOUT_SECONDS` | `20` | Timeout for provider requests |
| `JOB_REFRESH_ENABLED` | `true` | Runs the timed job import inside the API process |
| `JOB_REFRESH_INTERVAL_HOURS` | `6` | Hours between automatic imports |
| `JOB_REFRESH_ON_STARTUP` | `false` | Import once when the API starts |
| `JOB_REFRESH_MAX_PER_SOURCE` | `60` | Listings imported per source in one refresh |
| `JOB_REFRESH_MIN_INTERVAL_SECONDS` | `600` | Cooldown before another manual refresh is accepted |
| `RESUME_AI_ENABLED` | `false` | Sends extracted resume text to Groq when true |
| `GROQ_API_KEY`, `GROQ_MODEL` | Empty, `openai/gpt-oss-20b` | Groq credential and model |
| `GROQ_TIMEOUT_SECONDS`, `GROQ_MAX_CHARS` | `30`, `20000` | Groq timeout and text limit |
| `LANGCHAIN_EXPLANATIONS_ENABLED` | `false` | Enables the optional explanation stack |
| `APPLICATION_DRAFTS_AI_ENABLED` | `false` | Enables AI application drafts |

Always-allowed CORS origins are `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, and `http://127.0.0.1:5173`, plus `FRONTEND_URL`. Any other host, including a LAN address or a staging domain, must be added through `FRONTEND_URL`.

### Frontend

Copy `frontend/.env.example` to `frontend/.env.local`:

| Variable | Default | Effect |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | API origin used by the browser |
| `VITE_SUPABASE_URL` | Empty | Supabase Auth project URL; forms show a configuration message when absent |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Empty | Browser-safe Supabase publishable/anon key |

Only browser-safe values belong in `VITE_*` variables, because Vite inlines them into the bundle. Never place `DEV_JOB_WRITE_KEY`, `DATABASE_URL`, `GROQ_API_KEY`, or a Supabase secret/service-role key there. The frontend never sends the development key, and key-gated routes stay unavailable until the backend validates real user identity.

Supabase setup, route-level behavior, and integration boundaries are documented in [docs/frontend.md](docs/frontend.md). The full test plan is in [docs/testing.md](docs/testing.md).

## API overview

All profile endpoints use `/api/v1/candidates`. FastAPI provides request validation and interactive documentation at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check that the API responds |
| `GET` | `/health/db` | Check database connectivity |
| `GET` | `/api/v1/jobs` | List and filter jobs |
| `GET` | `/api/v1/jobs/{job_id}` | Get one active job |
| `POST` | `/api/v1/jobs` | Create a job (development key required) |
| `POST` | `/api/v1/candidates` | Create a candidate profile (owned by the verified account when a token is sent) |
| `GET` | `/api/v1/candidates/me` | Get the profile owned by the verified account |
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

Most create operations return `201`; delete operations return `204`. Missing candidates or child records return `404`. Invalid input generally returns `422`; empty partial updates return `400`; duplicate conflicts may return `409`. Candidate-scoped routes require a verified Supabase access token and answer `404` for another account's record. In development the private feature routers also accept `X-Dev-Job-Key`; outside development that key is refused and the request answers `401`. Development operations (`/api/v1/ops/*`, job creation) keep the development-only key. See `/docs` for the detailed request and response schemas, [docs/auth-and-ownership.md](docs/auth-and-ownership.md) for identity rules, and [docs/frontend.md](docs/frontend.md) for the complete exported endpoint inventory.

### Resume review and import

Upload a PDF or DOCX as multipart form data in the `file` field to the preview endpoint. Files must be at most 5 MiB and have a matching filename extension and content type. Password-protected PDFs and files with no extractable text are not supported. The endpoint returns extracted contact details, skills, experience, education, parser information, and warnings; it does not store the file or modify the candidate profile.

By default, the local parser is used. It recognizes a fixed skill catalog and common resume section layouts, so results may be incomplete. Optional Groq extraction can be enabled with `RESUME_AI_ENABLED=true` and a `GROQ_API_KEY`; in that mode, extracted resume text is sent to Groq. The service validates returned fields against source text and falls back to local parsing when Groq is unavailable. Review all results before importing.

Send selected records to the import endpoint as JSON with `"approved": true`. The import API rejects unapproved requests, requires at least one selected record, and reports created and skipped counts. It avoids duplicate skills and duplicate experience or education records. Preview and import are separate requests: the import endpoint accepts reviewed data; it does not itself verify that the supplied details came from a prior preview.

## Multi-Source Job Discovery

The job importer reads ten public providers:

| Provider | Endpoint | Flag |
| --- | --- | --- |
| Greenhouse | Job Board API | `--greenhouse-board` |
| Lever | Postings API | `--lever-site` + `--lever-company-name` |
| Ashby | Job board API | `--ashby-board token` or `--ashby-board "token:Company Name"` |
| Workable | Widget API | `--workable-site site` or `--workable-site "site:Company Name"` |
| SmartRecruiters | Postings API | `--smartrecruiters-company id` |
| Remotive | Remote job feed | `--feed remotive` |
| Arbeitnow | Job board feed | `--feed arbeitnow` |
| Jobicy | Remote job feed | `--feed jobicy` |
| Remote OK | Remote job feed | `--feed remoteok` |
| Himalayas | Remote job feed | `--feed himalayas` |

Provider adapters normalize their listings into the shared job schema. Each imported listing retains its provider (`source`) and provider-specific identifier (`source_job_id`), along with its original `job_url` and normalized `canonical_url`.

The ingestion pipeline canonicalizes URLs and checks existing jobs by provider identity and canonical URL. It also checks company/title/location fingerprints for likely cross-provider duplicates; possible duplicates are skipped and reported. Both providers use the same `jobs` table, which can be hosted on PostgreSQL or Supabase.

The importer defaults to a dry run and does not commit database changes unless `--apply` is passed. From the `backend` directory, for example:

```powershell
python -m app.scripts.ingest_jobs --defaults
python -m app.scripts.ingest_jobs --defaults --apply
python -m app.scripts.ingest_jobs --ashby-board "openai:OpenAI" --workable-site "huggingface:Hugging Face" --apply
python -m app.scripts.ingest_jobs --feed remotive --feed arbeitnow --apply
```

`--defaults` imports from the curated, verified catalog in `backend/app/services/job_sources/catalog.py`: 18 Greenhouse boards, 2 Lever sites, 14 Ashby boards, one Workable account, one SmartRecruiters company and all five public feeds. Every flag may be repeated. Each source is fetched and imported on its own, so an unreachable board is reported under "Sources that could not be imported" instead of discarding the listings already collected. `--max-per-source` (default 120) bounds one run; each source is imported newest first. The command uses `DATABASE_URL` from the repository-root `.env`. Review the dry-run summary before applying imports.

Jobicy and Remote OK ask that they are credited as the source; imported listings keep their `job_url` pointing at the provider page.

### Keeping listings fresh

The API refreshes the job pool itself, so the listings do not go stale between manual imports.

- In the app, open **Jobs** and use **Refresh listings now**. The panel follows the run and reloads the list when it finishes.
- `POST /api/v1/jobs/refresh` starts a run and returns `202` immediately. It needs a verified access token, or `X-Dev-Job-Key` in development, and answers `409` while another run is in progress or during the cooldown.
- `GET /api/v1/jobs/refresh/status` reports the latest run: counts, per-source failures and whether one is running.
- The API process also imports on a timer (`JOB_REFRESH_INTERVAL_HOURS`, default 6 hours). The timer lives in the API process, so the API has to stay running for automatic refreshes to happen; a manual refresh works either way.

Every run also closes listings that have disappeared. A job is deactivated (`is_active = false`) once no provider returns it any more, so the job list only shows roles that still exist. Only providers that answered in the run are considered, so a board that is down or comes back empty never hides its roles, and a role that is still published by a second provider stays visible. A closed role is reactivated automatically if an employer publishes it again. The command-line importer applies the same rule when it runs with `--apply`.

Only one refresh runs at a time, and a run is bounded by `JOB_REFRESH_MAX_PER_SOURCE` (default 60 per source). Set `JOB_REFRESH_ENABLED=false` to turn the timer off, `JOB_REFRESH_ON_STARTUP=true` to import once at startup, and `JOB_REFRESH_MIN_INTERVAL_SECONDS` to change the manual cooldown. The command-line importer keeps working independently of these settings.

## Database migrations

The ORM defines candidate profiles, skills, work experiences, educations, jobs, applications, application drafts and status events, submission handoffs, follow-ups and their events, interviews and interview notifications, job embeddings, and notification recovery runs.

Alembic is configured in `alembic.ini` and loads its URL from `DATABASE_URL`. Two consecutive revisions, `fa05578eada4` and `5b0bd740df7a`, both create `candidate_profiles`; therefore, upgrading a clean database to head is expected to fail. The candidate migration columns and constraints also do not fully match the model. Repair and test the migration history before using it to create or update a database. Inspect generated migrations and back up important data before applying schema changes.

For local testing, create a disposable SQLite database from the ORM metadata instead; the exact commands are in [docs/testing.md](docs/testing.md#2-create-a-disposable-local-database). Never point that flow at a shared or production database.

## Development checks

Run backend tests and lint from the repository root:

```powershell
python -m pytest
python -m ruff check .
```

Run frontend checks from `frontend/`:

```powershell
npm run lint
npm run format:check
npm run typecheck
npm run test
npm run build
npx playwright install chromium
npm run test:e2e
```

Backend tests cover health checks, model and schema behavior, resume validation/parsing/analysis, Groq fallback behavior, reviewed resume import, job ingestion, matching, workflows, applications, follow-ups, interviews, and SQLite-backed persistence. The current suite reports 464 passing tests, including the identity and ownership cases in `backend/tests/test_auth_ownership.py`; Ruff reports no findings. Frontend checks currently report zero lint warnings, 36 Vitest tests, a successful production build, and four passing Playwright scenarios across desktop Chromium and an iPhone 13 viewport.

The browser suites run the sample journey only. Server JWT verification and cross-account ownership are covered by backend pytest tests, not by the browser suites. Real email delivery, real resume upload from the browser, and candidate persistence against a production database are not comprehensively integration-tested.

The full local QA plan, including mobile emulation, a real phone on the same network, API smoke requests, CORS checks, and release exit criteria, is in [docs/testing.md](docs/testing.md).

## Docker

`compose.yaml` builds the API image and publishes it on `127.0.0.1` only. It reads the root `.env` at runtime:

```powershell
docker compose up -d --build api
docker compose exec api python -m app.scripts.smoke_deployment --skip-database
docker compose down
```

The frontend is not part of the Compose stack; run it with Vite and point `VITE_API_BASE_URL` at the published API port.

## Security status and next work

The remaining gates before any public deployment are:

- ~~Validate Supabase JWTs in FastAPI, map the verified subject to a candidate, and enforce ownership on every candidate-scoped record and file.~~ Implemented in `backend/app/core/auth.py`; configure `SUPABASE_URL` or the JWKS values and run the two-account checks on staging.
- ~~Replace the development-key gate on the workflow, application, handoff, follow-up, interview, and notification routers.~~ Implemented; development operations keep the development-only key.
- Repair the Alembic history and test clean-database upgrade and downgrade paths, including the new `d26auth01` owner column.
- Configure `LANGGRAPH_CHECKPOINT_URL` so workflow checkpoints and notification scheduling no longer depend on process memory.
- Configure the real HTTPS origins in `FRONTEND_URL`, Supabase site/redirect URLs, and the frontend build, then replace the static-host examples with the chosen host's configuration.
- Complete privacy, retention, and deletion handling before storing real profile or resume data.

Until then, keep the API on loopback or a private network and use synthetic data.

## Documentation

- [Architecture](docs/architecture.md) — job discovery design.
- [Roadmap](docs/roadmap.md) — current status and suggested priorities.
- [Technical stack](docs/technical-stack.md) — dependencies, settings, and persistence.
- [Frontend](docs/frontend.md) — routes, architecture, API boundaries, and deployment notes.
- [Authentication and ownership](docs/auth-and-ownership.md) — verified identity, ownership rules, and the development gate.
- [Production readiness](docs/production-readiness.md) — why the workspace was demo-only, the live wiring, and the release checklist.
- [Testing](docs/testing.md) — local QA plan for desktop and mobile.
- [CI/CD](docs/ci-cd.md) — GitHub Actions workflows and release rules.
