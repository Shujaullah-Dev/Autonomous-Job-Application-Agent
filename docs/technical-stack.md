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

The root `requirements.txt` is the project dependency manifest. There is no `backend/requirements.txt`, frontend package manifest, lockfile, Docker configuration, or CI workflow in the repository.

`pyproject.toml` configures pytest to discover `backend/tests` and adds `backend` to the Python path. Ruff uses an 88-character line length, Python 3.11 lint target, and the `E`, `F`, `I`, `B`, and `UP` rule groups.

## Configuration

Settings are loaded from process environment variables and the repository-root `.env`. `DATABASE_URL` is required. Unknown settings are ignored.

| Variable | Default | Effect |
| --- | --- | --- |
| `APP_NAME` | `AI Job Agent` | FastAPI title |
| `APP_ENV` | `development` | Loaded but not currently used by application behavior |
| `DEBUG` | `false` | FastAPI debug mode |
| `API_HOST` | `127.0.0.1` | Loaded setting; Uvicorn host is configured separately |
| `API_PORT` | `8000` | Loaded setting; Uvicorn port is configured separately |
| `DATABASE_URL` | Required | SQLAlchemy connection and Alembic URL |
| `GROQ_API_KEY` | Empty | Groq API credential |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq model name |
| `RESUME_AI_ENABLED` | `false` | Enables Groq resume analysis when true |
| `GROQ_TIMEOUT_SECONDS` | `30.0` | Groq request timeout |
| `GROQ_MAX_CHARS` | `20000` | Maximum resume text length sent to Groq |

`.env.example` contains additional values for planned services; they are not consumed by the application. It sets `RESUME_AI_ENABLED=true`, unlike the code default. Review that value before enabling Groq: resume text is sent to the provider.

## Persistence

The API uses SQLAlchemy's synchronous engine and creates one session per request. Models use the declarative base in `backend/app/db/base.py`. Alembic configuration is in `alembic.ini`; migration scripts are in `backend/alembic/versions`.

Current ORM tables:

- `candidate_profiles`: UUID, name, unique/indexed email, optional phone/location/summary/experience, timestamps.
- `candidate_skills`: candidate foreign key, name, proficiency, timestamp; unique per candidate and skill name.
- `work_experiences`: candidate foreign key, employer/title, dates, current flag, optional location/description.
- `educations`: candidate foreign key, institution/degree, dates, optional field/description.
- `jobs`: integer ID, title, company, description, unique URL, optional location/source/employment type.

The profile detail tables cascade on candidate deletion. The job model has no relationship to a candidate and no API endpoints. There are no application, user, match, interview, or stored-resume tables.

**Migration warning:** revisions `fa05578eada4` and `5b0bd740df7a` both create `candidate_profiles`; a fresh upgrade is expected to fail. Some candidate migration fields and constraints also do not match the ORM model. Repair and test migrations before provisioning or upgrading important databases.

## Resume processing

Resume uploads are validated as PDF or DOCX, limited to 5 MiB, and parsed in memory. The API does not store the uploaded file. Local extraction uses `pypdf` and `python-docx`; local analysis relies on recognized headings/layouts and a fixed skill catalog. If enabled, Groq receives the extracted text. Returned details are checked against source text and local analysis is used when Groq is unavailable. The result remains best-effort and requires user review.

## Not implemented

There is no frontend, job-source integration, job ingestion, matching, AI-generated application materials, application tracking, authentication, background worker, Redis integration, notification/calendar provider, or deployment stack. Add tools for these only when a specific feature requires them.
