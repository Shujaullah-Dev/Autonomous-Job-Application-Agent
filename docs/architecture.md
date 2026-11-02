# Architecture

This document separates the implemented backend from the product's future direction.

## Current system

```text
HTTP client
    │
    ▼
FastAPI (backend/app/main.py)
    ├── Health checks
    └── /api/v1/candidates
          ├── Candidate profile routes
          ├── Skills, experience, and education routes
          ├── Resume preview ── PDF/DOCX extraction ── local parser
          │                                      └──── optional Groq extraction
          └── Reviewed resume import
                         │
                         ▼
                 SQLAlchemy sessions ── PostgreSQL
```

The app registers the candidate, skill, experience, education, and resume routers. Each request that accesses the database receives a synchronous SQLAlchemy session through `get_db`; the session is closed after the request. Routes and services perform database operations directly; there is no separate repository layer. Alembic migrations are managed separately from application startup.

### Main modules

| Location | Responsibility |
| --- | --- |
| `backend/app/main.py` | Creates the FastAPI application, registers routers, and defines health checks |
| `backend/app/core/config.py` | Loads settings from environment variables and the repository-root `.env` |
| `backend/app/api/routes/` | Candidate, skill, experience, education, resume preview, and resume import endpoints |
| `backend/app/schemas/` | Pydantic request and response validation |
| `backend/app/models/` | SQLAlchemy models for profile, skills, experience, education, and jobs |
| `backend/app/services/` | Resume validation, text extraction, analysis, normalization, and import |
| `backend/app/db/` | Declarative base, engine, and request-scoped sessions |
| `backend/alembic/` | Migration environment and schema revisions |

## Resume processing flow

1. The client uploads a PDF or DOCX to `POST /api/v1/candidates/{candidate_id}/resume/preview`.
2. The API checks that the candidate exists, validates the upload (maximum 5 MiB), and extracts text. Files are not persisted.
3. If `RESUME_AI_ENABLED` is true, the service tries Groq. It checks returned values against text evidence and falls back to local parsing if the provider is unavailable. Otherwise, the local parser is used.
4. The preview response contains contact details, skills, experience, education, parser information, and warnings. Extraction is best-effort; the user must review it.
5. The client submits selected records to `POST /api/v1/candidates/{candidate_id}/resume/import` with `approved: true`. The API creates new records and skips duplicates.

The import endpoint requires an explicit approval flag, but it does not prove that the submitted records came from a prior preview. Optional Groq analysis sends extracted resume text to the provider; configure this only when that transfer is acceptable.

## Data model

- `CandidateProfile`: UUID, name, unique email, optional contact and profile fields, timestamps.
- `CandidateSkill`: candidate UUID, name, proficiency level, timestamp; unique by candidate and name.
- `WorkExperience`: candidate UUID, employer, title, dates, current-employment flag, optional location and description.
- `Education`: candidate UUID, institution, degree, dates, optional field of study and description.
- `Job`: integer ID, title, company, description, unique URL, optional source/location/employment type.

Skills, experience, and education reference candidate profiles with cascading deletes. `Job` has no relationship to a candidate. There are no user/account, resume-file, application, match, or interview tables, and no job routes.

## Migration status

Alembic uses `Base.metadata` and the configured `DATABASE_URL`. The revision chain contains consecutive revisions `fa05578eada4` and `5b0bd740df7a` that both create `candidate_profiles`; a fresh upgrade to head is expected to fail. Some candidate migration columns and constraints also differ from the current ORM model. Repair and test the migration history before relying on it for database setup.

## Future product design

The intended product may grow to include authorized job-source adapters, normalization, explainable matching, user-reviewed application drafts, and application tracking. These features are not implemented. No frontend, worker, queue, job-source integration, application-submission workflow, notification service, or calendar integration is present.

Keep integrations replaceable and matching independently testable. Do not bypass source terms, authentication, CAPTCHA, rate limits, or other access controls. Require explicit user approval for consequential actions.

## Current limitations

- There is no authentication or authorization; candidate routes are not safe to expose as a multi-user service.
- Resume preview is best-effort and does not store the uploaded file.
- Local resume parsing recognizes common layouts and a fixed technical-skill catalog; it can miss details.
- AI output is not guaranteed to be correct even when checked against source text.
- Migration history must be repaired and tested before fresh-database provisioning.

## Tests

The test suite includes health checks, model and schema validation, skills/experience/education rules, resume validation and parsing, extraction fallback, and import behavior. It does not comprehensively test the migration chain or production-database operations.
