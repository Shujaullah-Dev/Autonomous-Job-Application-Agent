
"""Python CI workflow contract tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/backend-ci.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_backend_ci_workflow_exists():
    assert WORKFLOW.is_file()


def test_backend_ci_runs_on_pull_requests_and_main():
    text = workflow_text()

    assert "pull_request:" in text
    assert "push:" in text
    assert "main" in text


def test_backend_ci_uses_python_312():
    text = workflow_text()

    assert 'python-version: "3.12"' in text


def test_backend_ci_runs_tests_and_lint():
    text = workflow_text()

    assert "python -m pytest -q" in text
    assert "python -m ruff check ." in text
    assert "python -m pip check" in text


def test_backend_ci_checks_migration_heads():
    text = workflow_text()

    assert "ScriptDirectory.from_config" in text
    assert "len(heads) != 1" in text


def test_backend_ci_does_not_apply_migrations():
    text = workflow_text()

    assert "alembic upgrade head" not in text


def test_backend_ci_does_not_use_live_secrets():
    text = workflow_text()

    assert "secrets.DATABASE_URL" not in text
    assert "secrets.GROQ_API_KEY" not in text
    assert "permissions:" in text
    assert "contents: read" in text
    assert "persist-credentials: false" in text
