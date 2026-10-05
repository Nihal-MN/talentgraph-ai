"""Shared test fixtures.

Hermetic by default (throwaway SQLite file); set ``TEST_DATABASE_URL`` to run
the same suite against PostgreSQL + pgvector (CI does both). The environment
is configured *before* any app import so the engine binds correctly. Each
session seeds a small deterministic dataset (60 profiles) through the real
seed path — tests never point at the demo database.
"""

from __future__ import annotations

import os
import tempfile

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
else:
    _TMPDIR = tempfile.mkdtemp(prefix="talentgraph-tests-")
    os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"
os.environ["AI_PROVIDER"] = "demo"
os.environ["OPENAI_API_KEY"] = ""

import pytest  # noqa: E402
from sqlalchemy import text as sa_text  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.seed.run_seed import _clear_all, seed  # noqa: E402

TEST_COUNT = 60


@pytest.fixture(scope="session")
def seeded() -> dict:
    import app.models  # noqa: F401 — register all tables

    with engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            # the vector column type needs the extension before CREATE TABLE
            connection.execute(sa_text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        _clear_all(db)
        summary = seed(db, count=TEST_COUNT, with_benchmark=False)
    return summary


@pytest.fixture()
def db(seeded: dict):
    with SessionLocal() as session:
        yield session


@pytest.fixture()
def client(seeded: dict):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
