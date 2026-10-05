"""System health — live database, embedding mode, vector backend. No secrets."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select, text

from app import __version__
from app.api.deps import DbSession
from app.core.config import get_settings
from app.models import Candidate, Company, EmbeddingMetadata, Job, SavedSearch, SearchQuery, Skill

router = APIRouter()


@router.get("/health")
def health(db: DbSession) -> dict:
    settings = get_settings()
    database_status = "ok"
    dialect = None
    detail = None
    counts: dict = {}
    try:
        dialect = db.get_bind().dialect.name
        counts = {
            "candidates": db.scalar(select(func.count()).select_from(Candidate)),
            "companies": db.scalar(select(func.count()).select_from(Company)),
            "skills": db.scalar(select(func.count()).select_from(Skill)),
            "embeddings": db.scalar(select(func.count()).select_from(EmbeddingMetadata)),
            "jobs": db.scalar(select(func.count()).select_from(Job)),
            "saved_searches": db.scalar(select(func.count()).select_from(SavedSearch)),
            "searches_logged": db.scalar(select(func.count()).select_from(SearchQuery)),
        }
    except Exception as exc:  # noqa: BLE001 — health must never crash the app
        database_status = "error"
        detail = str(exc)[:200]

    from app.services.embedding import get_embedding_provider
    from app.services.query_parser import get_query_parser

    try:
        provider = get_embedding_provider()
        embedding = {"provider": provider.name, "dims": provider.dims}
    except Exception as exc:  # noqa: BLE001
        embedding = {"provider": "unavailable", "dims": None, "detail": str(exc)[:200]}

    pgvector_verified = False
    if dialect == "postgresql":
        try:
            pgvector_verified = (
                db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()
                is not None
            )
        except Exception:  # noqa: BLE001
            pgvector_verified = False

    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "app": settings.app_name,
        "version": __version__,
        "database": {"status": database_status, "dialect": dialect, "detail": detail},
        "ai": {
            "mode": settings.resolved_ai_mode,
            "embedding": embedding,
            "query_parser": get_query_parser().name,
            "api_key_configured": bool(settings.openai_api_key),
        },
        "retrieval": {
            "vector_backend": "pgvector" if dialect == "postgresql" else "python-cosine",
            "lexical_backend": "postgres-fts" if dialect == "postgresql" else "bm25-python",
            "fusion": f"rrf(k={settings.rrf_k})",
            "pgvector_verified": pgvector_verified,
        },
        "counts": counts,
    }
