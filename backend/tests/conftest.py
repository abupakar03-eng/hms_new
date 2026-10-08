"""Shared pytest fixtures.

The DATABASE_URL is redirected to a throw-away SQLite file *before* the
application package is imported, because ``backend.database`` builds the engine
at import time.
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

_TMP_DB = Path(tempfile.gettempdir()) / "hospital_os_test.db"
if _TMP_DB.exists():
    _TMP_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB.as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ADMIN_PASSWORD"] = "Admin@123"
# Keep bcrypt cheap during tests.
os.environ["BCRYPT_ROUNDS"] = "4"
# The suite issues thousands of requests from a single client address, so the
# per-IP limiter would reject the tests themselves. Rate limiting has its own
# focused test that drives the limiter directly.
os.environ["RATE_LIMIT_MAX_REQUESTS"] = "100000"

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # ``with`` is required so that the lifespan (migrations + admin bootstrap) runs.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def admin_headers(client):
    response = client.post("/login", data={"username": "admin", "password": "Admin@123"})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture()
def patient(client, admin_headers):
    response = client.post(
        "/patients/",
        json={
            "name": "Regression Patient",
            "age": 34,
            "gender": "Male",
            "phone": "9876500001",
            "blood_group": "B+",
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def lab_test(client, admin_headers):
    import uuid

    code = f"T-CBC-{uuid.uuid4().hex[:8].upper()}"
    response = client.post(
        "/lab-test-masters/",
        json={
            "test_code": code,
            "test_name": f"Test Complete Blood Count {code}",
            "category": "Haematology",
            "sample_type": "Blood",
            "unit": "g/dL",
            "reference_range": "13 - 17",
            "price": 300.0,
            "tat_hours": 6,
            "parameters": [
                {
                    "name": "Haemoglobin",
                    "unit": "g/dL",
                    "reference_range": "13 - 17",
                    "critical_low": 7.0,
                    "display_order": 0,
                },
                {"name": "WBC", "unit": "cells/uL", "reference_range": "4000 - 11000", "display_order": 1},
            ],
        },
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()
