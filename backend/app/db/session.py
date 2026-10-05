"""Engine + session factory. PostgreSQL (+pgvector) in Docker; SQLite fallback
for development and hermetic tests (vector math then runs in Python)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_settings = get_settings()
_url = _settings.resolved_database_url

if _url in ("sqlite://", "sqlite:///:memory:"):
    _engine = create_engine(
        _url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
elif _url.startswith("sqlite"):
    _engine = create_engine(_url, connect_args={"check_same_thread": False})
else:
    _engine = create_engine(_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
engine = _engine


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
