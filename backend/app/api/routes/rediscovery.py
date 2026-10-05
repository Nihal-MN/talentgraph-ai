"""Talent Rediscovery — paste a JD, search the existing pool for matches."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.api.schemas import RediscoveryIn
from app.models import Job
from app.services.normalize import (
    detect_seniority,
    expand_skills,
    extract_skills,
    find_location,
    parse_years,
)
from app.services.search_service import SearchRequest, run_search
from app.services.taxonomy import DOMAIN_KEYWORDS

router = APIRouter()


def parse_jd(jd_text: str, title: str | None) -> dict:
    """Deterministic JD parse: skills, seniority, years, domain, location."""
    skills = [match["canonical"] for match in extract_skills(jd_text, max_skills=12)]
    lowered = jd_text.lower()
    domains = [
        industry
        for industry, keywords in DOMAIN_KEYWORDS.items()
        if any(keyword in lowered for keyword in keywords)
    ]
    location = find_location(jd_text)
    return {
        "skills": skills,
        "expansions": [skill for skill in expand_skills(skills) if skill not in skills],
        "min_years": parse_years(jd_text),
        "seniority": detect_seniority(jd_text),
        "domains": domains[:3],
        "location": location,
        "title_family": None,
        "title": title,
    }


@router.post("/rediscovery")
def rediscovery(payload: RediscoveryIn, db: DbSession) -> dict:
    parsed = parse_jd(payload.jd_text, payload.title)

    job = Job(
        title=payload.title or "Pasted JD",
        company_name=payload.company_name,
        description_text=payload.jd_text,
        parsed=parsed,
        source="paste",
    )
    db.add(job)
    db.flush()

    # Build the search query from the JD: skills + up to six salient words from
    # the first 500 chars of free text (deterministic, no LLM needed).
    query_parts = list(parsed["skills"])
    if parsed.get("location") and parsed["location"].get("city"):
        query_parts.append(parsed["location"]["city"])
    query_parts.extend(
        word.strip(".,;:()").lower()
        for word in payload.jd_text[:500].replace("\n", " ").split()
        if len(word) > 6
    )
    query_text = " ".join(dict.fromkeys(query_parts))[:400]

    outcome = run_search(
        db,
        SearchRequest(
            raw_query=query_text or payload.title or "candidate",
            filters={},
            strategy="hybrid",
            limit=payload.limit,
            rerank=True,
            job_id=job.id,
        ),
    )

    # gaps: JD skills with no match in the result set
    top_skill_sets = [set(result["skills"]) for result in outcome["results"][:10]]
    gaps = [
        skill
        for skill in parsed["skills"]
        if not any(skill in skill_set for skill_set in top_skill_sets)
    ]

    db.commit()
    return {
        "job": {"id": job.id, "title": job.title, "company_name": job.company_name},
        "parsed_jd": parsed,
        "search": {
            "query": outcome["parsed"]["raw"],
            "strategy": outcome["strategy"],
            "took_ms": outcome["took_ms"],
            "total": outcome["total"],
        },
        "matches": outcome["results"],
        "gaps": gaps,
        "note": "Deterministic JD parsing; ranking explained per result. Human recruiters decide.",
    }


@router.get("/rediscovery/jobs/{job_id}")
def job_detail(job_id: int, db: DbSession) -> dict:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"No job {job_id}.")
    return {
        "id": job.id,
        "title": job.title,
        "company_name": job.company_name,
        "description_text": job.description_text,
        "parsed": job.parsed,
        "created_at": job.created_at.isoformat(),
    }
