
from unittest.mock import MagicMock

from app.db.session import get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_database_health_returns_connected() -> None:
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "connected",
    }


def test_database_health_returns_503_on_db_error() -> None:
    db = MagicMock()
    db.execute.side_effect = SQLAlchemyError("simulated failure")
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get("/health/db")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "status": "error",
            "database": "unavailable",
        }
    }