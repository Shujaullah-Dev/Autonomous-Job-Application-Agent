# Architecture

This document distinguishes the architecture that exists in the repository today from the target product design. The target architecture is aspirational; only the components listed under [Implemented system](#implemented-system) currently exist.

## Implemented system

```text
HTTP client
    │
    ▼
FastAPI application (backend/app/main.py)
    ├── GET /health
    ├── GET /health/db ──────────────┐
    └── /api/v1/candidates           │
           │                         │
           ├── Pydantic schemas      │
           ├── Candidate SQLAlchemy model
           └── get_db dependency ────┴── SQLAlchemy Session / PostgreSQL

SQLAlchemy models: CandidateProfile, Job
Alembic: intended schema migrations (candidate migration history needs repair)
```

The FastAPI app registers the candidate router and two health endpoints. The database session dependency creates one SQLAlchemy session per request and closes it when the request ends. Candidate endpoint handlers perform database reads/writes directly; there is no service or repository layer yet.

### Implemented modules

| Location | Responsibility |
| --- | --- |
| `backend/app/main.py` | Creates the FastAPI app, registers candidate routes, exposes health checks |
| `backend/app/core/config.py` | Loads settings from environment and `.env`; `DATABASE_URL` is required |
| `backend/app/api/routes/candidates.py` | Candidate create, fetch-by-ID, and partial-update operations |
| `backend/app/schemas/candidate.py` | Validates candidate input and serializes responses |
| `backend/app/models/candidate.py` | SQLAlchemy mapping for `candidate_profiles` |
| `backend/app/models/job.py` | SQLAlchemy mapping for `jobs` |
| `backend/app/db/base.py` | Shared SQLAlchemy declarative base |
| `backend/app/db/session.py` | Engine, session factory, and FastAPI database dependency |
| `backend/alembic/` | Alembic environment and versioned schema changes |

### Request and persistence flow

For a candidate request, FastAPI validates the body using the corresponding Pydantic schema and injects a database session via `get_db`. The route performs the query or mutation using the SQLAlchemy model, commits writes, and returns a response validated against `CandidateResponse`. Create and update operations roll back on `IntegrityError` and return HTTP 409. Missing profiles return 404. No table creation is performed at API startup.

The health endpoint `/health` does not query the database. `/health/db` runs `SELECT 1` and returns 503 if a SQLAlchemy database error occurs.

### Current data model

`CandidateProfile` stores a UUID, full name, unique/indexed email, optional phone, location, professional summary and years of experience, plus timestamps. `Job` stores a database ID, title, company name, optional location/source/employment type, description, unique job URL, and timestamps.

At present, there are no ORM relationships between these models. There is no candidate list/delete endpoint, no job endpoint, no application entity, and no resume entity.

### Migration status

Alembic loads metadata from `Base` and obtains the connection URL from application settings. The migration chain contains one jobs-table revision followed by two candidate-profile revisions that both create the same table. As a result, provisioning a fresh database by upgrading to the latest revision is expected to fail on the duplicate creation. Candidate migration definitions also do not fully reflect model-level length, uniqueness/index, and text column constraints. Repair and test the migration chain before using it as a reliable schema bootstrap.

## Target product architecture

The intended product is a modular, user-directed assistant. A potential future decomposition is:

```text
Web client (not implemented)
          │ REST
          ▼
FastAPI API
   ├── Candidate / resume management
   ├── Job discovery and normalization
   ├── Matching and recommendations
   ├── Application-material drafting
   └── Application and interview tracking
          │
          ├── PostgreSQL persistence
          ├── Optional background worker / queue
          ├── Optional LLM provider
          └── Optional calendar / notification providers
```

Do not interpret this diagram as deployed services. The repository currently has no frontend, worker, queue, LLM integration, job-source adapter, notification provider, or calendar integration.

### Intended user workflow

1. A user supplies profile information and, eventually, a resume.
2. The system extracts or records structured candidate information for user review.
3. The system obtains jobs only from sources that permit the access method.
4. Jobs are normalized and deduplicated before being stored or shown.
5. Deterministic requirements and explainable scoring rank possible matches.
6. Optional AI components can assist with semantic interpretation and drafting, with their output validated.
7. The user reviews recommendations and generated materials.
8. The system takes no consequential application action without explicit user approval.
9. The user can track applications, interviews, deadlines, and reminders.

Steps 1–9 describe the target, not current behavior.

## Future component boundaries

When the product grows, keep source-specific integrations and provider-specific behavior behind replaceable interfaces. A future job-source adapter should normalize records into a shared job representation; matching should be testable independently of any LLM; and document generation should produce drafts for user review rather than submitting them automatically.

Introduce background work only when a concrete task is too slow for a request/response cycle. The current system has no Redis, queue, or worker. Likewise, authentication, authorization, file storage, audit history, and production observability have not yet been implemented and are prerequisites for handling real user data safely.

## Safety and reliability principles

- Keep secrets in local environment configuration; do not commit `.env`.
- Validate all external and user-provided data.
- Use authorized job sources and honor terms, rate limits, and access controls.
- Do not bypass CAPTCHA, authentication, anti-bot protections, or platform restrictions.
- Require explicit user approval before submitting an application or taking another consequential action.
- Prefer deterministic and explainable logic for validation, scoring, deduplication, and state transitions.
- Test any future AI features for unsupported claims and malformed output.

## Testing strategy

The existing suite tests health responses using a mocked database and asserts selected `Job` model metadata. It does not currently provide integration coverage of candidate persistence or migrations.

As implementation expands, add focused unit tests for schemas and services, database integration tests for persistence and migrations, and end-to-end tests for complete user-visible workflows. AI evaluation datasets and ranking/generation quality metrics are future work.
