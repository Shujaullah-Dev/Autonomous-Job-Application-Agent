# Project Roadmap

This roadmap describes code that exists today. Configuration placeholders and product goals do not count as implemented features.

## Current status

| Capability | Status | Notes |
| --- | --- | --- |
| FastAPI backend and health checks | Implemented | `/health` and `/health/db` |
| Candidate profiles | Implemented | Create, get by UUID, and partial update |
| Candidate skills | Implemented | Create, list, update, and delete |
| Work experience | Implemented | Create, list, update, and delete |
| Education | Implemented | Create, list, update, and delete |
| Resume preview | Implemented | PDF/DOCX validation, text extraction, local analysis, optional Groq |
| Reviewed resume import | Implemented | Requires `approved: true`; skips duplicates |
| Job persistence | Implemented | Greenhouse and Lever ingestion with deduplication; search, detail, and key-gated create routes |
| Database migrations | Configured, needs repair | Two revisions create the candidate table; model and migration differ |
| Tests | Implemented | 443 backend tests plus frontend lint, type, unit, build, and browser checks |
| Job search and recommendations | Implemented | Filters, pagination, matching, hybrid matching, and explanations |
| Application preparation and tracking | Implemented | Workflows, drafts, revisions, status history, handoffs, follow-ups, and interviews |
| Authentication and authorization | Implemented backend | Supabase JWT verification, candidate `owner_id`, `/api/v1/candidates/me`, ownership on every candidate-scoped router; see `docs/auth-and-ownership.md` |
| Durable workflow checkpoints | Implemented, needs a PostgreSQL database | `LANGGRAPH_CHECKPOINT_URL` selects `PostgresSaver`; unset means the in-process saver |
| Frontend | Implemented | React and Vite workspace with demo journey, live job reads, and candidate profile writes |
| Notifications, calendar, deployment, CI | Partially implemented | Interview notifications, `.ics` export, Docker packaging, and four GitHub Actions workflows; no hosted deployment |

## Recommended priorities

### 1. Make database setup reliable

- Repair the duplicate candidate-profile revisions.
- Align migration definitions with ORM constraints and fields.
- Add clean-database upgrade and downgrade tests.
- Document and verify the supported PostgreSQL connection driver.

### 2. Add access control before real user data

- ~~Define user identity and profile ownership.~~ Done: `candidate_profiles.owner_id` and `/api/v1/candidates/me`.
- ~~Implement authentication and authorization on every candidate-scoped endpoint.~~ Done: verified JWTs plus `require_candidate_owner`; two-account tests exist.
- Configure `SUPABASE_URL`/JWKS values and run the two-account checks on staging before real user data is stored.
- Define privacy, retention, logging, and deletion policies for profile and resume data.
- Restrict deployment exposure until these controls exist.

### 3. Strengthen current API coverage

- Add persistence integration tests for candidate, skill, experience, and education APIs.
- Test database constraints, failure behavior, and all endpoint response contracts.
- Document supported resume layouts and improve extraction based on representative test fixtures.
- Make the resume import approval/review flow clear to clients.

### 4. Build job discovery and matching

- Add schemas and CRUD endpoints for the existing job model if needed.
- Select a permitted job source and implement a small source adapter.
- Normalize and deduplicate listings; document source terms and rate limits.
- Start with deterministic matching and explainable reasons.

### 5. Add application workflow and product experience

- Model applications and status history before adding tracking routes.
- Keep generated material as a draft; validate claims and require user approval.
- Add a frontend after API contracts stabilize.
- Add notifications, calendar connections, background work, CI, and deployment only when their requirements are clear.

## Product target

```text
Candidate profile and reviewed resume data
    → permitted job discovery
    → normalized listings
    → explainable recommendations
    → user-reviewed application drafts
    → explicit approval
    → application and interview tracking
```

Profile management, resume review/import, job discovery, matching, workflows, application tracking, follow-ups, interviews, and notifications are implemented. Private browser access to those later features, and verified candidate ownership, are not. Do not bypass provider terms, access controls, or anti-bot protections. Consequential actions must remain under user control.

Local verification steps, including desktop and mobile testing, are in `docs/testing.md`.

## Definition of done

For each feature, update this roadmap and related documentation. A feature is complete when its API behavior and error cases are documented and tested, its database changes have tested migrations, and privacy and access-control risks are addressed.
