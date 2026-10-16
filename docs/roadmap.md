# Project Roadmap

This roadmap reflects the repository's current implementation, rather than the original day-by-day schedule. A feature is marked **Implemented** only when corresponding code exists. Planned product capabilities are not implied by the architecture diagrams or environment-template variables.

## Current snapshot

| Capability | Status | Notes |
| --- | --- | --- |
| Python project setup | Implemented | `pyproject.toml`, root and backend requirements files |
| FastAPI application | Implemented | App is in `backend/app/main.py` |
| API health checks | Implemented | `/health` and `/health/db` |
| Candidate profile persistence | Partially implemented | SQLAlchemy model, schemas, create/read-by-ID/patch endpoints |
| Job persistence model | Model only | `Job` schema is represented in SQLAlchemy; no API or ingestion exists |
| Alembic | Configured, needs repair | Candidate profile table is created by two revisions in succession |
| Automated tests | Initial | Health tests and job metadata tests; no candidate DB integration tests |
| Resume upload/parsing | Not implemented | No upload route, document parser, or resume model |
| Job discovery | Not implemented | No source integration, ingestion, normalization, or deduplication |
| Job matching/recommendations | Not implemented | No scoring service or matching endpoint |
| LLM / agent workflow | Not implemented | No LLM provider, LangChain, or LangGraph code |
| Application preparation/tracking | Not implemented | No application model or endpoints |
| Frontend | Not implemented | No frontend source or package manifest |
| Authentication/authorization | Not implemented | Candidate routes are currently unauthenticated |
| Notifications/calendar | Not implemented | Template placeholders only; no integrations |
| Docker / deployment / CI | Not implemented | No compose or workflow configuration is present |

## Recommended next steps

The order below prioritizes a usable and reliable backend foundation before adding larger product features.

### 1. Stabilize database setup

- Consolidate the duplicate candidate-profile migration into a valid migration history.
- Align the migration columns and constraints with the SQLAlchemy model.
- Ensure downgrade functions are meaningful and safe for the supported workflow.
- Add a migration test against a clean database.
- Verify the configured PostgreSQL driver and connection URL in a development setup.

### 2. Complete candidate-profile API quality

- Add tests for create, fetch, update, validation, not-found, and duplicate-email behavior.
- Exercise persistence against a test database rather than relying only on mocked sessions.
- Decide whether list/delete operations and profile ownership are in scope.
- Add authentication and authorization before exposing real candidate information.

### 3. Build a vertical job-data slice

- Add job request/response schemas and API behavior for the existing `Job` model.
- Choose one permitted job source and document its terms/access method.
- Implement source-specific fetching behind a small adapter, then validate and normalize records.
- Define and test deduplication behavior using source identifiers and/or canonical URLs.
- Add database and endpoint tests.

### 4. Add explainable matching

- Start with deterministic criteria and explicit match reasons.
- Keep ranking logic independently testable; do not require an LLM for basic recommendations.
- Add representative fixtures and quality checks for expected ranking behavior.

### 5. Add resume and application preparation

- Define secure resume storage, accepted formats, size limits, and retention behavior before enabling uploads.
- Parse supported documents into a reviewable candidate profile.
- Add generation only after choosing a provider boundary and validating output for unsupported claims.
- Keep generated materials as drafts and require explicit user approval for consequential actions.

### 6. Add application lifecycle, user experience, and operations

- Model applications and status history before implementing tracking endpoints.
- Add interviews, deadlines, reminders, and optional calendar/notification integrations as independently testable components.
- Add a frontend only after the API contracts are stable.
- Add Docker-based development, CI checks, authentication, logging, and deployment configuration as their needs become concrete.

## Product target

The desired end-to-end flow is:

```text
Candidate profile / resume
    → permitted job discovery
    → normalized and deduplicated listings
    → explainable recommendations
    → user-reviewed application drafts
    → explicit user approval
    → application and interview tracking
    → optional reminders and calendar events
```

This is a product goal, not a description of current functionality. Automated access must respect provider terms, rate limits, and technical controls; the system must not bypass CAPTCHA, authentication, or anti-bot protections.

## Definition of done

For each feature, update this roadmap and relevant documentation when code is added. A feature should not be considered complete until its behavior is tested, its error cases are handled, its data changes are migrated, and its user-facing contract is documented. Before handling real user data, security, access control, privacy, and retention behavior must be addressed.
