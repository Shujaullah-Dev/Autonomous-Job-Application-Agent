"""Container configuration contract tests."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_file(filename: str) -> str:
    return (ROOT / filename).read_text(encoding="utf-8")


def test_dockerfile_exists():
    assert (ROOT / "Dockerfile").is_file()


def test_compose_exists():
    assert (ROOT / "compose.yaml").is_file()


def test_dockerfile_uses_nonroot_user():
    dockerfile = read_file("Dockerfile")

    assert "USER app" in dockerfile
    assert "10001" in dockerfile


def test_dockerfile_has_healthcheck():
    dockerfile = read_file("Dockerfile")

    assert "HEALTHCHECK" in dockerfile
    assert "/health" in dockerfile


def test_container_has_one_worker():
    dockerfile = read_file("Dockerfile")

    assert '"--workers", "1"' in dockerfile


def test_no_secrets_copied_into_image():
    dockerfile = read_file("Dockerfile")
    dockerignore = read_file(".dockerignore")

    assert "COPY . ." not in dockerfile
    assert "COPY .env" not in dockerfile
    assert ".env" in dockerignore
    assert ".venv" in dockerignore


def test_compose_binds_only_to_loopback():
    compose = read_file("compose.yaml")

    assert "127.0.0.1:" in compose
    assert "env_file:" in compose


def test_compose_uses_supabase_not_local_database():
    compose = read_file("compose.yaml")

    assert "\n  postgres:" not in compose
    assert "\n  redis:" not in compose


def test_compose_enables_security_settings():
    compose = read_file("compose.yaml")

    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "huggingface_cache:" in compose


def test_migrations_are_not_run_at_api_startup():
    dockerfile = read_file("Dockerfile")

    assert "alembic upgrade head" not in dockerfile