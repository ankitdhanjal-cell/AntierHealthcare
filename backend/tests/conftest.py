"""Tests rebuild the database, so they only run against a separate TEST_DATABASE_URL (never your dev data).

Create one, e.g. with the local Postgres:   createdb ahs_test
Then:   TEST_DATABASE_URL=postgresql+psycopg2://...@.../ahs_test pytest
"""
import os
import tempfile

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_URL:
    pytest.skip("Set TEST_DATABASE_URL to a throwaway database to run these tests", allow_module_level=True)
os.environ["DATABASE_URL"] = TEST_URL
os.environ["EVIDENCE_DIR"] = tempfile.mkdtemp(prefix="ahs-test-evidence-")  # never touch the dev evidence folder


@pytest.fixture(scope="session")
def db():
    from app.db import SessionLocal
    from app.seed import rebuild
    with SessionLocal() as s:
        rebuild(s)
        yield s


@pytest.fixture(scope="session")
def client(db):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    token = c.post("/api/auth/login", json={"email": "quality.manager@hospital.example", "password": "Sandbox@2026"}).json()["token"]
    c.headers.update({"authorization": f"Bearer {token}"})
    return c
