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
| Job persistence | Model only | No job API or ingestion |
| Database migrations | Configured, needs repair | Two revisions create the candidate table; model and migration differ |
| Tests | Initial coverage | Unit/schema and SQLite-backed resume-import coverage; migration chain needs tests |
| Job search and recommendations | Not implemented | No source adapters, ingestion, or matching |
| Application preparation and tracking | Not implemented | No generation, application, or interview models/routes |
| Authentication and authorization | Not implemented | API endpoints are unauthenticated |
| Frontend | Not implemented | No frontend project |
| Notifications, calendar, deployment, CI | Not implemented | No integrations or infrastructure configuration |

## Recommended priorities

### 1. Make database setup reliable

- Repair the duplicate candidate-profile revisions.
- Align migration definitions with ORM constraints and fields.
- Add clean-database upgrade and downgrade tests.
- Document and verify the supported PostgreSQL connection driver.

### 2. Add access control before real user data

- Define user identity and profile ownership.
- Implement authentication and authorization on every candidate-scoped endpoint.
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

Only profile management and resume review/import are currently implemented. Do not bypass provider terms, access controls, or anti-bot protections. Consequential actions must remain under user control.

## Definition of done

For each feature, update this roadmap and related documentation. A feature is complete when its API behavior and error cases are documented and tested, its database changes have tested migrations, and privacy and access-control risks are addressed.
