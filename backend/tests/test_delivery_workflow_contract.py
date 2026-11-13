
"""Docker CI and publishing workflow contract tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONTAINER_CI = ROOT / ".github/workflows/container-ci.yml"
PUBLISH = ROOT / ".github/workflows/publish-image.yml"


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_delivery_workflows_exist():
    assert CONTAINER_CI.is_file()
    assert PUBLISH.is_file()


def test_container_ci_runs_on_pull_requests():
    content = read_file(CONTAINER_CI)

    assert "pull_request:" in content
    assert "push:" in content
    assert "main" in content


def test_container_ci_never_publishes_image():
    content = read_file(CONTAINER_CI)

    assert "push: false" in content
    assert "packages: write" not in content
    assert "docker push " not in content


def test_container_ci_runs_smoke_test():
    content = read_file(CONTAINER_CI)

    assert "smoke_deployment" in content
    assert "--skip-database" in content
    assert "docker compose config --quiet" in content
    assert "docker compose up -d --no-build api" in content


def test_container_ci_uses_dummy_settings():
    content = read_file(CONTAINER_CI)

    assert "ci-placeholder-not-secret" in content
    assert "secrets.DATABASE_URL" not in content
    assert "secrets.GROQ_API_KEY" not in content


def test_publishing_is_manual_only():
    content = read_file(PUBLISH)

    assert "workflow_dispatch:" in content
    assert "\n  pull_request:" not in content
    assert "\n  push:" not in content
    assert "confirm_publish" in content


def test_publishing_requires_main_branch():
    content = read_file(PUBLISH)

    assert "refs/heads/main" in content
    assert "inputs.confirm_publish == true" in content


def test_publishing_uses_limited_registry_token():
    content = read_file(PUBLISH)

    assert "packages: write" in content
    assert "secrets.GITHUB_TOKEN" in content
    assert "smoke_deployment" in content
    assert 'docker push "${IMAGE}:sha-${GITHUB_SHA}"' in content


def test_no_automatic_migrations_or_live_submission():
    for path in (CONTAINER_CI, PUBLISH):
        content = read_file(path)

        assert "alembic upgrade head" not in content
        assert "apply-to-job" not in content
        assert "secrets.GROQ_API_KEY" not in content
