# Technical Stack

This page describes technologies that are present in the repository separately from ideas that remain under consideration. A package being listed in a requirements file does not mean a product feature using it has been implemented.

## Runtime and developer tooling

| Technology | Current use | Status |
| --- | --- | --- |
| Python (>= 3.10.2) | Backend runtime requirement in `pyproject.toml` | Configured |
| pip / `requirements.txt` | Python dependency installation | Configured |
| FastAPI | REST API framework | Used |
| Uvicorn | ASGI server | Declared; used to run the app |
| Pydantic | Request/response data validation | Used by schemas and FastAPI |
| Pydantic Settings | Environment-backed configuration | Used |
| SQLAlchemy 2.x | ORM, engine, and database sessions | Used |
| Alembic | Database schema migrations | Configured; migration history needs repair |
| PostgreSQL drivers | `psycopg2-binary` in root dependencies; `psycopg` additionally in `backend/requirements.txt` | Declared; verify the driver required by the chosen connection URL |
| pytest | Automated tests | Configured |
| Ruff | Linting/import sorting | Configured |
| FastAPI `TestClient` | API endpoint tests | Used in tests |
| Git / GitHub | Source control and hosting | Repository is hosted; no CI workflow is present in the tree |

`pyproject.toml` configures pytest to search `backend/tests` and adds `backend` to the Python path. Ruff uses an 88-character line length, targets Python 3.11 for lint rules, and enables `E`, `F`, `I`, `B`, and `UP` rule groups.

## Dependency manifests

- The repository-root `requirements.txt` is the general install manifest.
- `backend/requirements.txt` currently repeats the root list and adds `psycopg`.
- Both manifests include FastAPI, Uvicorn, Pydantic Settings, pytest, Ruff, `httpx2`, SQLAlchemy, Alembic, and `psycopg2-binary`.
- `httpx2` is declared as a dependency, but there is no external HTTP integration in the current application.

Keep the manifests aligned intentionally when dependencies change. The project does not currently have a frontend package manifest, Docker configuration, or a lockfile.

## Configuration

`backend/app/core/config.py` defines these settings:

| Setting | Default / requirement | Current effect |
| --- | --- | --- |
| `APP_NAME` | `AI Job Agent` | FastAPI title |
| `APP_ENV` | `development` | Loaded, but not otherwise used |
| `DEBUG` | `false` | FastAPI debug option |
| `API_HOST` | `127.0.0.1` | Loaded; the Uvicorn command must still be configured separately |
| `API_PORT` | `8000` | Loaded; the Uvicorn command must still be configured separately |
| `DATABASE_URL` | Required | SQLAlchemy database connection and Alembic URL |

Settings are read from the process environment and `.env` in the current working directory; unknown environment keys are ignored. `.env.example` also contains values for future PostgreSQL provisioning, Redis, security, LLM, frontend, notifications, and calendar features. Those are placeholders and are not consumed by the current application.

## Persistence

The application uses SQLAlchemy's synchronous engine and sessions. `get_db` yields one session per request and closes it afterward. `Base` is the declarative base used by models. Alembic is configured in root `alembic.ini`, with migrations under `backend/alembic/`.

Current ORM tables:

- `candidate_profiles` — UUID ID, required name and unique/indexed email, optional phone/location/summary/experience, timestamps.
- `jobs` — integer ID, required title/company/description/unique URL, optional location/source/employment type, timestamps.

There are no relationships between the tables and no application, resume, user, match, or interview tables. Candidate migration revisions currently both create `candidate_profiles`; the migration chain must be fixed and tested before treating Alembic as a working fresh-database bootstrap.

## Not implemented (future evaluation)

The following technologies or capabilities have been discussed as options but are not implemented in the current repository:

| Area | Options / direction | Current status |
| --- | --- | --- |
| Frontend | React or Next.js with TypeScript | No frontend project |
| Resume processing | PDF/DOCX extraction libraries | No upload or parsing code |
| Job sources | Authorized APIs/feeds behind adapters | No source integration |
| Matching | Deterministic scoring first; semantic methods only if useful | No matching code |
| LLMs / agents | Provider abstraction; evaluate frameworks only when needed | No LLM, LangChain, or LangGraph code |
| Background processing | Add a worker/queue for tasks that warrant it | No Redis or worker |
| Notifications / calendar | Provider interfaces and mock implementations as needed | No integrations |
| Authentication / authorization | Required before real user data is exposed | Not implemented |
| Deployment | Docker/Compose and CI when development needs are defined | No configuration present |

Avoid adding infrastructure or AI dependencies before a concrete feature needs them. Keep consequential actions behind explicit user approval and respect external service terms and technical access controls.
