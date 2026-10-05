"""Indexing: build search text, embeddings and metadata for a candidate.

One code path used by the seed generator, the resume-ingestion pipeline and
`make reembed`, so the embedded content and its hash are always consistent.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Candidate, EmbeddingMetadata
from app.services.embedding import (
    content_hash,
    embedding_document,
    get_embedding_provider,
)


def build_search_text(candidate: Candidate, skill_names: list[str] | None = None) -> str:
    """The denormalized lexical surface (used by the SQLite BM25 fallback and
    as the PG full-text source)."""
    parts = [
        candidate.full_name,
        candidate.headline or "",
        candidate.seniority or "",
        candidate.summary or "",
        " ".join(skill_names or []),
        " ".join(
            f"{experience.title or ''} {experience.company.name if experience.company else ''}"
            for experience in candidate.experiences
        ),
        candidate.resume_text or "",
    ]
    return "\n".join(part for part in parts if part)


def index_candidate(db: Session, candidate: Candidate, force: bool = False) -> EmbeddingMetadata:
    """(Re)compute embeddings for a candidate when content changed (or force)."""
    skill_names = [skill.name_raw for skill in candidate.skills]
    document = embedding_document(
        {
            "headline": candidate.headline,
            "seniority": candidate.seniority,
            "skills": skill_names,
            "summary": candidate.summary,
            "resume_text": candidate.resume_text,
        }
    )
    digest = content_hash(document)
    provider = get_embedding_provider()

    metadata = candidate.embedding
    if (
        metadata
        and not force
        and metadata.content_hash == digest
        and metadata.model_name == provider.name
    ):
        return metadata
    vector = provider.embed([document])[0]

    if metadata is None:
        metadata = EmbeddingMetadata(candidate_id=candidate.id)
        db.add(metadata)
    metadata.model_name = provider.name
    metadata.dimensions = provider.dims
    metadata.content_hash = digest
    metadata.embedded_at = datetime.now(UTC)
    metadata.embedding = vector
    db.flush()
    return metadata
