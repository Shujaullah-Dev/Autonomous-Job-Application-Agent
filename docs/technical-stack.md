# Technical Stack

## Core programming languages and development tools

| Category | Technology | Purpose | Project status |
| --- | --- | --- | --- |
| Primary language | Python | Backend, AI logic, integrations, automation | Already selected |
| Frontend language | TypeScript | Type-safe frontend development | Planned |
| Frontend markup | HTML5 | Structure of web pages | Used through React |
| Frontend styling | CSS3 | Layout, responsive design, visual styling | Planned |
| Database query language | SQL | Database schema, queries, constraints and migrations | Already relevant |
| Version control | Git | Branches, commits, merges and collaboration | Already in use |
| Remote repository | GitHub | Code hosting, review, issues and project history | Already in use |
| Code editor | VS Code or existing IDE | Development and debugging | Development tool |
| Terminal | Git Bash / PowerShell | Running commands on Windows | Current environment |
| Python environment | venv | Isolating project dependencies | Recommended |
| Dependency management | pip with requirements.txt | Installing Python packages | Already selected |
| Frontend package manager | npm | Managing JavaScript dependencies | Planned |
| API testing | HTTPX and FastAPI TestClient | Testing API endpoints | Planned/partially configured |
| Code linting | Ruff | Python linting and style checks | Already declared |
| Automated testing | pytest | Unit and integration tests | Already declared |

## Backend technology stack

The backend is the central part of the application. It receives requests, coordinates the AI services, applies business rules, and interacts with Supabase.

| Technology / library | Purpose in our project | Status |
| --- | --- | --- |
| FastAPI | Build REST API endpoints | Already declared in requirements |
| Uvicorn | Run the FastAPI application | Already declared |
| Pydantic | Validate request and response data | Used by the FastAPI stack |
| Pydantic Settings | Load application configuration and environment variables | Already declared |
| SQLAlchemy 2.x | ORM, SQL execution and database engine | Already declared |
| Psycopg 3 | PostgreSQL database driver | Already declared |
| Alembic | Version-controlled schema migrations | Already declared |
| HTTPX | Make HTTP requests to external services and test APIs | Dependency needs review |
| Python logging | Record runtime events and errors | Planned implementation |
| Python asyncio | Asynchronous I/O where appropriate | Available; usage to be decided |
| FastAPI dependency injection | Manage request-scoped database sessions and services | Planned/verify existing implementation |
| FastAPI lifespan | Manage application startup and shutdown | Planned/verify existing implementation |

## Database and persistence stack

This is the most immediate part of our roadmap because we are replacing the local Docker PostgreSQL server.

| Technology / component | Purpose | Status |
| --- | --- | --- |
| PostgreSQL | Relational database engine | Selected |
| Supabase | Managed cloud PostgreSQL platform | Selected; integration verification pending |
| Supabase SQL Editor / Connect panel | Inspect database, schema and connection details | Operational tool |
| SQLAlchemy | Database access from Python | Already declared |
| Psycopg 3 | Python-to-PostgreSQL connectivity | Already declared |
| Alembic | Database schema versioning | Already declared; setup needs verification |
| SQL migrations | Reproducible schema changes | Required workflow |
| Database indexes and constraints | Query performance and data integrity | Planned per schema |
| Supabase Row Level Security (RLS) | Enforce row access policies where appropriate | Planned security design |
| Supabase Storage | Store resumes and generated documents if appropriate | Optional planned component |
| Supabase Auth | User authentication if it fits our architecture | Evaluate before implementation |
| Supabase connection pooling | Manage database connections when appropriate | Use based on deployment and connection pattern |
| Database backups | Recovery from accidental loss or corruption | Must be configured and verified against the selected plan |

## Proposed core database entities

| Table / entity | Information stored | Planned phase |
| --- | --- | --- |
| users | User identity reference and account metadata | Authentication |
| candidate_profiles | Candidate preferences, experience and profile metadata | Profile management |
| skills | Normalized skill catalog | Profile management |
| candidate_skills | Candidate-to-skill relationships | Profile management |
| resumes | Resume metadata, file reference and parsed content | Resume management |
| companies | Employer information | Job ingestion |
| jobs | Job title, description, source, location and status | Job ingestion |
| job_skills | Skills associated with jobs | Job matching |
| job_matches | Candidate/job scores and match explanations | AI matching |
| generated_documents | Resume variants and cover-letter drafts | Document generation |
| applications | Application status, timestamps and job association | Application tracking |
| application_events | History of status changes and workflow actions | Workflow orchestration |
| user_approvals | Approval state for consequential actions | Human-in-the-loop workflow |

## AI and machine-learning stack

We should start with the smallest useful AI stack rather than installing several frameworks at once. Our system needs to make relevant job recommendations and prepare accurate application materials—not merely call an LLM.

| Technology / library | Purpose | Decision |
| --- | --- | --- |
| LLM provider interface | Keep the application independent of a single model provider | Required design |
| Local LLM runtime | Run models on a developer's machine | Optional; current LLM_PROVIDER=local needs implementation verification |
| Hosted LLM API | Generate structured results and application drafts | Optional; select after cost and privacy evaluation |
| Pydantic schemas | Validate structured AI outputs | Recommended |
| Rule-based scoring | Assess hard requirements, location, experience and skills | Build first |
| Embeddings | Represent job descriptions and candidate profiles semantically | Planned, only if useful |
| Vector search | Retrieve semantically similar jobs or skill descriptions | Optional |
| pgvector | Store and query vector embeddings in PostgreSQL | Optional Supabase extension |
| LlamaIndex or LangChain | Higher-level LLM orchestration and integrations | Defer unless actual complexity justifies it |
| Prompt templates | Standardize matching and document-generation instructions | Planned |
| Evaluation datasets | Test relevance, consistency and output quality | Required |
| AI output validation | Detect unsupported qualifications, malformed results and missing fields | Required |
| Token/cost tracking | Monitor hosted model usage and cost | Required if using paid APIs |

## Job discovery and external integrations

The agent needs reliable job data. We should prioritize permitted APIs and feeds before introducing browser automation.

| Technology / component | Purpose | Status |
| --- | --- | --- |
| HTTPX | Call authorized job APIs | Planned; dependency needs review |
| JSON | Parse structured API responses | Standard Python support |
| RSS/Atom parsing library | Ingest job feeds when available | Optional |
| Pydantic | Validate incoming job records | Recommended |
| Source adapters | Isolate each job board's integration logic | Required design |
| Normalization logic | Standardize titles, locations, skills and dates | Planned |
| Deduplication | Avoid storing the same vacancy multiple times | Required |
| Scheduled ingestion | Fetch new and updated vacancies periodically | Planned |
| API rate limiting and retries | Respect provider limits and recover from transient failures | Required |
| Playwright | Browser automation for permitted workflows | Optional later |
| Beautiful Soup | Parse permitted HTML content | Optional later |
| Selenium | Alternative browser automation framework | Defer unless needed |

## Background jobs and workflow automation

Job ingestion, resume processing, and application tracking can eventually run outside the normal API request lifecycle.

| Technology / component | Purpose | Decision |
| --- | --- | --- |
| FastAPI background tasks | Small, noncritical background operations | Suitable initially |
| APScheduler or equivalent scheduler | Run periodic job ingestion | Evaluate |
| Redis | Cache, coordination or queue backend | Not yet confirmed as necessary |
| Celery | Distributed task queue | Defer until workload justifies it |
| RQ or Dramatiq | Alternative background task systems | Evaluate only if needed |
| Idempotency keys | Prevent duplicate processing and submissions | Required for critical workflows |
| Retry policy | Recover from transient failures | Required |
| Application state machine | Enforce valid status transitions | Required |
| Audit trail | Record important workflow events | Required |
| Human approval gate | Prevent unapproved consequential actions | Required |

## Frontend stack

The frontend is a planned part of the product, not a prerequisite for completing Day 3.

| Technology | Purpose | Status |
| --- | --- | --- |
| React | Component-based user interface | Proposed |
| TypeScript | Type safety and maintainability | Proposed |
| Vite | Development server and build tooling | Proposed |
| HTML5 | Page structure | Standard web platform |
| CSS3 | Styling and responsive layouts | Proposed |
| Tailwind CSS | Utility-based styling | Optional |
| React Router | Navigation between screens | Proposed if needed |
| TanStack Query | API fetching, caching and mutation state | Optional, recommended as complexity grows |
| React Hook Form | Form state and validation | Optional |
| Zod | Runtime validation of frontend data | Optional |
| Fetch API | HTTP communication with FastAPI | Sufficient initially |
| Playwright | End-to-end browser tests | Planned for later testing |

## Resume processing and document generation

| Technology / library | Purpose | Status |
| --- | --- | --- |
| python-docx | Read and generate Word documents | Evaluate |
| pypdf | Extract text from text-based PDFs | Evaluate |
| PyMuPDF (fitz) | Advanced PDF text extraction and layout handling | Alternative to evaluate |
| OCR engine | Extract text from scanned resumes | Optional |
| Pydantic | Validate structured candidate profile data | Recommended |
| Jinja2 | Populate reusable document templates | Optional |
| LLM provider | Generate tailored content | Planned |
| DOCX/PDF export pipeline | Produce downloadable application materials | Planned |
| Supabase Storage | Store original resumes and generated files | Optional, subject to security design |

## Testing and quality assurance

| Technology / method | Purpose | Status |
| --- | --- | --- |
| pytest | Unit and integration test runner | Already declared |
| HTTPX | Test FastAPI endpoints | Dependency needs review |
| FastAPI TestClient | Exercise endpoints through tests | Available through FastAPI's testing ecosystem |
| Ruff | Linting and code-quality checks | Already declared |
| Alembic migration tests | Validate schema upgrade paths | Planned |
| SQLAlchemy test fixtures | Set up and clean up test data | Planned |
| Mock LLM provider | Test AI workflows without API costs | Recommended |
| Mock external API responses | Test job ingestion reliably | Recommended |
| Playwright | End-to-end browser testing | Planned |
| GitHub Actions | Run automated checks on pushes and pull requests | Planned |
| Coverage.py / pytest-cov | Measure test coverage | Optional |
| Structured logging | Diagnose failures without exposing sensitive data | Planned |

## Security, privacy and configuration

| Component / practice | Purpose | Status |
| --- | --- | --- |
| .env | Local secrets and configuration | Already in use |
| .env.example | Document required variables without secrets | Already in use; correction required |
| .gitignore | Prevent committing secrets and generated files | Already established; verify |
| SECRET_KEY | Application-specific cryptographic secret where needed | Already declared; implementation needs review |
| HTTPS/TLS | Encrypt traffic between clients and services | Required |
| Supabase credentials | Connect to the database with appropriate permissions | Required |
| Database roles and least privilege | Limit the impact of credential exposure | Required |
| Supabase RLS | Enforce appropriate row-level access | Planned where applicable |
| Authentication | Verify user identity | Planned |
| Authorization | Limit actions and data access by user and role | Planned |
| Password hashing | Secure password storage if managing passwords ourselves | Only if applicable; prefer managed authentication where suitable |
| Rate limiting | Limit abusive or excessive requests | Planned |
| Input validation | Reject malformed or invalid data | Required |
| Audit logs | Record consequential workflow operations | Required |
| Secret rotation | Recover from accidental credential exposure | Required operational procedure |
| Backup and recovery testing | Protect persistent data | Required |

## Deployment, hosting and operations

| Technology / service | Purpose | Status |
| --- | --- | --- |
| Supabase | Managed database | Selected |
| Managed Python hosting | Host the FastAPI backend | To select |
| Static frontend hosting | Host the built React frontend | To select |
| GitHub Actions | Automated checks and deployment workflows | Planned |
| Docker | Reproducible environment or deployment where useful | Optional |
| Environment variables / secrets manager | Supply deployment configuration securely | Required |
| HTTPS | Secure public endpoints | Required |
| Application health endpoint | Check backend availability | Planned |
| Centralized logs | Diagnose runtime problems | Planned |
| Monitoring and alerts | Detect outages and failures | Planned |
| Supabase backup facilities | Database recovery | Verify against plan |
| Error reporting service | Capture production exceptions | Optional |
| Domain and DNS | Public application URL | Later phase |

## Complete software inventory: current versus future

This consolidated table is the reference for what the team should install, verify, or defer.

| Software / library | Current decision | Immediate action |
| --- | --- | --- |
| Python | Core backend language | Confirm team version |
| FastAPI | Core API framework | Retain |
| Uvicorn | API server | Retain |
| Pydantic Settings | Configuration | Verify .env loading |
| SQLAlchemy | Database access | Retain |
| Psycopg 3 | PostgreSQL driver | Retain |
| Alembic | Schema migrations | Verify env.py and migration history |
| Supabase | Cloud database | Finish connection verification |
| pytest | Testing | Expand relevant tests |
| Ruff | Linting | Run checks |
| Git / GitHub | Version control | Continue branch workflow |
| HTTPX | HTTP client and API testing | Investigate httpx2 dependency |
| React / TypeScript / Vite | Frontend | Defer until backend is ready |
| LLM provider | AI generation | Define provider interface and initial strategy |
| Embeddings / pgvector | Semantic matching | Defer until needed |
| Resume parsing libraries | Document ingestion | Evaluate in resume phase |
| Redis | Cache/queue support | Verify actual code usage |
| Celery / RQ / Dramatiq | Background jobs | Defer |
| Playwright | Browser automation/testing | Defer until an approved use case |
| GitHub Actions | Continuous integration | Add after local tests stabilize |
| Hosting provider | Backend/frontend deployment | Decide in deployment phase |
| Monitoring / error reporting | Production operations | Add before public release |

## Technology ownership for both developers

Learning is mandatory for both developers, regardless of who implements a particular component.

| Work area | Developer A — primary implementation | Developer B — primary implementation | Required learning for both |
| --- | --- | --- | --- |
| Database | Supabase, SQLAlchemy, Psycopg, Alembic | Database integration tests and documentation | PostgreSQL, connection strings, migrations and sessions |
| Backend | Core API and database integration | Validation, testing and API reliability | FastAPI, Pydantic, HTTP and REST |
| Candidate profile | Models and persistence | Resume parsing and validation | Relational modeling and file handling |
| Job ingestion | Source adapters and storage | Normalization, deduplication and tests | HTTP APIs, JSON and data quality |
| AI matching | Scoring engine and model integration | Evaluation datasets and ranking tests | Prompt engineering, scoring and evaluation |
| Documents | Generation pipeline | Output validation and review workflows | Document parsing, LLM outputs and data integrity |
| Automation | Application workflow and persistence | Retry logic, audit logs and workflow tests | Idempotency, state machines and failure recovery |
| Frontend | Backend integration | UI implementation and browser tests | React, TypeScript and API integration |
| Deployment | Database and backend deployment | End-to-end tests and documentation | Secrets, monitoring, backups and security |