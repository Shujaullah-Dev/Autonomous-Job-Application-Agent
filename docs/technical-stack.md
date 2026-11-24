# Technical Stack

This page describes technologies used by the current code. A declared dependency does not mean every planned product feature exists.

## Runtime and tools

| Technology | Use |
| --- | --- |
| Python 3.10.2+ | Backend runtime (`pyproject.toml`) |
| FastAPI and Uvicorn | HTTP API and ASGI server |
| Pydantic and Pydantic Settings | Request/response validation and environment-backed settings |
| SQLAlchemy 2.x | ORM, synchronous engine, and database sessions |
| Alembic | Database schema migrations; current history needs repair |
| PostgreSQL drivers | `psycopg2-binary` and `psycopg` are declared in the root requirements |
| `pypdf`, `python-docx` | PDF and DOCX text extraction |
| `python-multipart` | Multipart file uploads |
| `httpx` | Groq API requests |
| pytest, FastAPI TestClient | Automated tests |
| Ruff | Lint and import sorting |
| Node 24 and npm | Frontend runtime and package manager |
| React 19 and React DOM 19 | Interface runtime |
| Vite 8 and TypeScript 5.9 | Dev server, bundler, and strict type checking |
| Tailwind CSS 4 | Styling and responsive layout |
| React Router 7 | Client routing and route guards |
| TanStack Query 5 | Live job request state and caching |
| React Hook Form and Zod | Form state and validation |
| Supabase JS 2 | Optional browser sign-in, recovery, and session refresh |
| Vitest and Testing Library | Frontend unit and UI tests |
| Playwright | Desktop Chromium and mobile-size browser journeys |

The root `requirements.txt` is the backend dependency manifest. The frontend is a separate npm project in `frontend/` with a committed `package-lock.json`. The repository also contains `Dockerfile`, `compose.yaml`, and four GitHub Actions workflows: `backend-ci`, `container-ci`, `frontend-ci`, and `publish-image`.

`pyproject.toml` configures pytest to discover `backend/tests` and adds `backend` to the Python path. Ruff uses an 88-character line length, Python 3.11 lint target, and the `E`, `F`, `I`, `B`, and `UP` rule groups.

## Configuration

Settings are loaded from process environment variables and the repository-root `.env`. `DATABASE_URL` is required. Unknown settings are ignored.

| Variable | Default | Effect |
| --- | --- | --- |
| `APP_NAME` | `AI Job Agent` | FastAPI title |
| `APP_ENV` | `development` | Key-gated writes return `403` when this is not `development` |
| `DEBUG` | `false` | FastAPI debug mode |
| `API_HOST` | `127.0.0.1` | Loaded setting; Uvicorn host is configured separately |
| `API_PORT` | `8000` | Loaded setting; Uvicorn port is configured separately |
| `DATABASE_URL` | Required | SQLAlchemy connection and Alembic URL |
| `GROQ_API_KEY` | Empty | Groq API credential |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq model name |
| `RESUME_AI_ENABLED` | `false` | Enables Groq resume analysis when true |
| `GROQ_TIMEOUT_SECONDS` | `30.0` | Groq request timeout |
| `GROQ_MAX_CHARS` | `20000` | Maximum resume text length sent to Groq |
| `DEV_JOB_WRITE_KEY` | Required | Development-only key for job creation and the private feature routers; refused outside `development` |
| `SUPABASE_URL` | Empty | Supabase project URL; derives the JWKS URL and expected token issuer |
| `SUPABASE_JWT_SECRET` | Empty | Legacy symmetric Supabase JWT secret for HS256 tokens |
| `SUPABASE_JWKS_URL` | Empty | Explicit JWKS URL when the project URL is not the API's identity origin |
| `SUPABASE_JWT_ISSUER` | Empty | Expected `iss` claim |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected `aud` claim |
| `LANGGRAPH_CHECKPOINT_URL` | Empty | PostgreSQL checkpoint URL for durable LangGraph workflow state |
| `FRONTEND_URL` | `http://localhost:3000` | First CORS origin; the local Vite origins are always allowed |
| `JOB_SOURCE_TIMEOUT_SECONDS` | `20.0` | Timeout for Greenhouse and Lever requests |
| `LANGCHAIN_EXPLANATIONS_ENABLED` | `false` | Enables the optional explanation stack |
| `APPLICATION_DRAFTS_AI_ENABLED` | `false` | Enables AI application drafts |

The CORS allowlist is `FRONTEND_URL` plus `http://localhost:3000`, `http://127.0.0.1:3000`, `http://localhost:5173`, and `http://127.0.0.1:5173`. Credentials are not allowed, and the `Authorization`, `Content-Type`, and `X-Dev-Job-Key` request headers are permitted. Any other browser origin, including a LAN or staging host, must be added through `FRONTEND_URL`.

`.env.example` sets `RESUME_AI_ENABLED=true`, unlike the code default. Review that value before enabling Groq: resume text is sent to the provider. Several template values (Redis, SMTP-style email, calendar, Docker host port) are placeholders for services the application does not yet contact.

## Frontend configuration

The frontend reads only `frontend/.env.local`, created from `frontend/.env.example`. Vite inlines these values at build time.

| Variable | Default | Effect |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000` | API origin used by browser requests |
| `VITE_SUPABASE_URL` | Empty | Supabase Auth project URL |
| `VITE_SUPABASE_PUBLISHABLE_KEY` | Empty | Browser-safe publishable/anon key |

No backend credential belongs in a `VITE_*` variable. The frontend never sends `X-Dev-Job-Key`. It does send the Supabase access token to the API, which verifies it before reading candidate data. Flow, error codes, ownership rules and key rotation are documented in [auth-and-ownership.md](auth-and-ownership.md).

## Identity and authorization

`backend/app/core/auth.py` verifies Supabase access tokens: signature (HS256 secret or JWKS), issuer, audience and expiry. Signing keys are cached for ten minutes and refreshed once when an unknown `kid` appears. Unreachable key material returns `503` without provider details.

A verified token resolves to a candidate through `candidate_profiles.owner_id`. `require_candidate_owner` is attached to every candidate-scoped router and answers `404` for another account's record. `require_private_access` replaced the development-key dependency on those routers: a token is accepted in any environment, while the development key works only in development. `/api/v1/ops/*` and job creation keep the development-only key.

## Persistence

The API uses SQLAlchemy's synchronous engine and creates one session per request. Models use the declarative base in `backend/app/db/base.py`. Alembic configuration is in `alembic.ini`; migration scripts are in `backend/alembic/versions`.

Current ORM tables:

- `candidate_profiles`: UUID, name, unique/indexed email, optional phone/location/summary/experience, unique optional `owner_id` (verified Supabase subject), timestamps.
- `candidate_skills`: candidate foreign key, name, proficiency, timestamp; unique per candidate and skill name.
- `work_experiences`: candidate foreign key, employer/title, dates, current flag, optional location/description.
- `educations`: candidate foreign key, institution/degree, dates, optional field/description.
- `jobs`: integer ID, title, company, description, unique URL, optional location/source/employment type.

The profile detail tables cascade on candidate deletion. The job model has no relationship to a candidate and no API endpoints. There are no application, user, match, interview, or stored-resume tables.

**Migration warning:** revisions `fa05578eada4` and `5b0bd740df7a` both create `candidate_profiles`; a fresh upgrade is expected to fail. Some candidate migration fields and constraints also do not match the ORM model. Repair and test migrations before provisioning or upgrading important databases.

## Resume processing

Resume uploads are validated as PDF or DOCX, limited to 5 MiB, and parsed in memory. The API does not store the uploaded file. Local extraction uses `pypdf` and `python-docx`; local analysis relies on recognized headings/layouts and a fixed skill catalog. If enabled, Groq receives the extracted text. Returned details are checked against source text and local analysis is used when Groq is unavailable. The result remains best-effort and requires user review.

## Frontend

The frontend is a Vite single-page application using React 19, strict TypeScript, React Router 7, Tailwind CSS 4, Radix Dialog, TanStack Query, React Hook Form, Zod, and Supabase Auth. It provides a complete in-browser sample journey, live job search and detail reads, and candidate profile writes after Supabase sign-in. Playwright covers desktop Chromium and an iPhone 13 viewport; Vitest covers validation, guards, and demo state rules. Details are in `docs/frontend.md`, and the local test plan is in `docs/testing.md`.

## Not implemented

The API verifies Supabase access tokens (HS256 secret or JWKS) and enforces candidate ownership: candidate-scoped routers require a verified owner, missing and foreign records both answer `404`, and `GET /api/v1/candidates/me` resolves the caller's profile. The development key remains a development-only gate and never establishes ownership. Not implemented: row-level security on the database, rate limiting and abuse controls, durable background jobs, Redis usage, a real email or calendar provider, and a hosted deployment. The shortlist, application, follow-up, interview and notification screens still read demo state. Details are in `docs/auth-and-ownership.md`; add tools for the rest only when a specific feature requires them.
