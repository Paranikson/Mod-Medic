"""HTTP API checks against the committed workspace fixtures."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import app

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _zip_fixture(name: str) -> io.BytesIO:
    folder = FIXTURES / name
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(folder))
    buf.seek(0)
    return buf


def test_validate_broken_returns_three_errors(client: TestClient):
    response = client.post(
        "/api/validate",
        files={"file": ("broken.zip", _zip_fixture("broken"), "application/zip")},
    )
    assert response.status_code == 200
    errors = [f for f in response.json()["findings"] if f["severity"] == "error"]
    assert len(errors) == 3
    assert {f["rule_id"] for f in errors} == {"E002", "E003", "E004"}


def test_validate_working_returns_no_errors(client: TestClient):
    response = client.post(
        "/api/validate",
        files={"file": ("working.zip", _zip_fixture("working"), "application/zip")},
    )
    assert response.status_code == 200
    errors = [f for f in response.json()["findings"] if f["severity"] == "error"]
    assert errors == []
    assert response.json()["counts"]["error"] == 0


def test_validate_non_zip_returns_400(client: TestClient):
    response = client.post(
        "/api/validate",
        files={"file": ("notes.txt", b"this is not a zip", "text/plain")},
    )
    assert response.status_code == 400


def test_health_returns_200(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
