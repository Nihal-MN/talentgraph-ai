"""Candidates: list, detail, and resume ingestion."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.deps import DbSession
from app.api.schemas import IngestIn
from app.models import Candidate, Skill
from app.services.ingestion import ingest_resume

router = APIRouter()


@router.get("/candidates")
def list_candidates(
    db: DbSession,
    response: Response,
    query: str | None = None,
    skill: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    statement = select(Candidate).options(joinedload(Candidate.location))
    if query:
        pattern = f"%{query}%"
        statement = statement.where(
            Candidate.full_name.ilike(pattern) | Candidate.headline.ilike(pattern)
        )
    if skill:
        subquery = select(Skill.candidate_id).where(Skill.name_raw.ilike(f"%{skill}%"))
        statement = statement.where(Candidate.id.in_(subquery))
    total = db.scalar(select(func.count()).select_from(statement.subquery()))
    response.headers["X-Total-Count"] = str(total or 0)
    rows = db.scalars(statement.order_by(Candidate.id).offset(offset).limit(limit)).unique().all()
    return [
        {
            "id": candidate.id,
            "full_name": candidate.full_name,
            "headline": candidate.headline,
            "seniority": candidate.seniority,
            "years_experience": candidate.years_experience,
            "location": candidate.location.label if candidate.location else None,
        }
        for candidate in rows
    ]


@router.get("/candidates/{candidate_id}")
def candidate_detail(candidate_id: int, db: DbSession) -> dict:
    candidate = (
        db.scalars(
            select(Candidate)
            .where(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.skills).selectinload(Skill.normalized_skill),
                selectinload(Candidate.experiences),
                selectinload(Candidate.educations),
                joinedload(Candidate.location),
                joinedload(Candidate.industry),
                joinedload(Candidate.embedding),
            )
        )
        .unique()
        .first()
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail=f"No candidate {candidate_id}.")

    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "headline": candidate.headline,
        "seniority": candidate.seniority,
        "years_experience": candidate.years_experience,
        "summary": candidate.summary,
        "location": candidate.location.label if candidate.location else None,
        "industry": candidate.industry.name if candidate.industry else None,
        "source": candidate.source,
        "skills": [
            {
                "name": skill.name_raw,
                "canonical": skill.normalized_skill.canonical_name
                if skill.normalized_skill
                else None,
                "category": skill.category,
                "evidence": skill.evidence,
            }
            for skill in candidate.skills
        ],
        "experiences": [
            {
                "title": experience.title,
                "normalized_title": experience.normalized_title,
                "start_date": experience.start_date.isoformat() if experience.start_date else None,
                "end_date": experience.end_date.isoformat() if experience.end_date else None,
                "is_current": experience.is_current,
            }
            for experience in candidate.experiences
        ],
        "educations": [
            {
                "degree": education.degree,
                "institution": education.institution,
                "year": education.year,
            }
            for education in candidate.educations
        ],
        "embedding": {
            "model": candidate.embedding.model_name,
            "dims": candidate.embedding.dimensions,
            "embedded_at": candidate.embedding.embedded_at.isoformat(),
        }
        if candidate.embedding
        else None,
    }


@router.post("/candidates/ingest", status_code=201)
def ingest(payload: IngestIn, db: DbSession) -> dict:
    candidate = ingest_resume(db, payload.resume_text, full_name=payload.full_name)
    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "headline": candidate.headline,
        "seniority": candidate.seniority,
        "years_experience": candidate.years_experience,
        "location": candidate.location.label if candidate.location else None,
        "skills_detected": len(candidate.skills),
        "note": "Ingested resumes are treated as untrusted data; ranking is deterministic.",
    }
