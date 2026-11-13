
#  CI/CD with GitHub Actions

## Purpose

Automatically validate the AI Job Agent on pull requests
and merges to main.

The pipeline checks Python code and Docker packaging,
then supports an explicitly manual image release.

It does not deploy a public application.

## Workflows

### Backend CI

File: `.github/workflows/backend-ci.yml`

Triggers:
- Pull requests targeting main
- Pushes to main
- Manual execution

Steps:
1. Checkout repository
2. Set up Python 3.12
3. Install requirements.txt
4. Check dependency compatibility
5. Run Ruff
6. Run the complete pytest suite
7. Confirm a single Alembic migration head

No live Supabase or Groq credentials are provided.

### Container CI

File: `.github/workflows/container-ci.yml`

Triggers:
- Pull requests targeting main
- Pushes to main
- Manual execution

Steps:
1. Checkout repository
2. Generate harmless CI-only settings
3. Validate compose.yaml
4. Build Dockerfile
5. Start the existing Compose API
6. Verify FastAPI /health
7. Verify OpenAPI route registration
8. Stop the temporary container

The container runs without live database access.
Therefore `/health/db` is not checked in this workflow.

### Publish Container Image

File: `.github/workflows/publish-image.yml`

Trigger:
- Manual workflow_dispatch only

Requirements:
- Select main branch
- Set confirm_publish=true
- Package publishing permissions must be available
- Review the passing main-branch checks first

Procedure:
1. Build image
2. Start and smoke-test image
3. Authenticate using GITHUB_TOKEN
4. Push image to GitHub Container Registry

Tag format:

ghcr.io/<owner>/<repository>:sha-<full-commit-sha>

Publishing is not deploying.

## Local validation

From the repository root:

```bash
python -m ruff check .
python -m pytest -q
python -m alembic heads
docker compose config --quiet
```

For a Docker runtime test:

```bash
docker compose up -d --build api
docker compose exec api \
  python -m app.scripts.smoke_deployment --skip-database
docker compose down
```

For a real Supabase connectivity check on the
developer's trusted local environment:

```bash
PYTHONPATH=backend \
  python -m app.scripts.smoke_deployment
```

## Security

- No Groq or Supabase secrets in PR workflows
- Read-only GITHUB_TOKEN for CI
- No pull_request_target workflow
- No automatic schema migration
- No automatic application submission
- No public production deployment
- GHCR publication is explicit and restricted to main
- Keep image packages private where appropriate
- Never commit .env
- Review third-party action versions and pin SHAs
  before high-assurance production release

## Known limitations

- Existing dependency file is not a full lockfile
- ML dependencies make Docker builds large
- Fresh-database Alembic migration history requires audit
- Candidate ownership authentication is incomplete
- LangGraph checkpoints remain process-local
- CI does not validate a real Supabase connection
- No external email or calendar-provider integration
- No production deployment workflow yet

## Troubleshooting

### Python CI fails

Open the Python tests and quality job.

Check:
- dependency installation
- Ruff output
- pytest traceback
- Alembic head validation

Fix the failing file and push the same PR branch.

### Container CI fails

Open the Docker build and smoke job.

Check:
- Dockerfile build step
- Compose configuration step
- Container logs
- API startup timeout
- Missing modules or runtime configuration

### Publish fails

Check:
- Workflow was started on main
- confirm_publish was selected
- GITHUB_TOKEN has packages:write permission
- Repository's package settings allow publishing
- Docker build and smoke test succeeded

## Release rule

A release candidate is acceptable only after:
- Backend CI passes
- Container CI passes
- Developers review the PR
- Main branch is updated
- Manual publication is explicitly authorized

A published image must not be considered production-ready
until the security and deployment requirements are met.
