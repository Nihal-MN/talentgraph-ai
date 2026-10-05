"""Resume ingestion — paste text → structured candidate through the same
normalization/embedding pipeline as the seed data. The text is treated as
untrusted data (parsed, quoted as evidence, never executed)."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models import Candidate, Company, Education, Experience, Location, NormalizedSkill, Skill
from app.services.indexing import build_search_text, index_candidate
from app.services.normalize import extract_skills, find_location, normalize_title, parse_years
from app.services.taxonomy import DOMAIN_KEYWORDS

_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-2]\d)\b")
_AT_COMPANY_RE = re.compile(r"\bat\s+([A-Z][\w&.\- ]{2,60})")
_CURRENT_YEAR = 2026


def _estimate_years(text: str) -> float | None:
    explicit = parse_years(text)
    if explicit is not None:
        return explicit
    years_found = [int(match) for match in _YEAR_RE.findall(text)]
    if not years_found:
        return None
    span = _CURRENT_YEAR - min(years_found)
    return float(min(max(span, 0), 40))


def _detect_industry(text: str) -> str | None:
    lowered = text.lower()
    for industry, keywords in DOMAIN_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return industry
    return None


def ingest_resume(db: Session, resume_text: str, full_name: str | None = None) -> Candidate:
    stripped = resume_text.strip()
    if len(stripped) < 30:
        raise AppError(
            ErrorCode.ingestion_failed, "Resume text is too short to parse (min 30 chars)."
        )

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    name = full_name or lines[0][:160]
    headline = None
    for line in lines[1:6]:
        lowered = line.lower()
        if any(
            word in lowered
            for word in (
                "engineer",
                "developer",
                "manager",
                "designer",
                "analyst",
                "recruiter",
                "specialist",
                "lead",
                "scientist",
                "consultant",
                "architect",
            )
        ):
            headline = line[:220]
            break
    title_info = normalize_title(headline or name)

    extraction = extract_skills(stripped, max_skills=30)
    if not extraction:
        raise AppError(
            ErrorCode.ingestion_failed,
            "No recognizable skills found — check that the resume text is complete.",
        )

    location_data = find_location(stripped)
    location = None
    if location_data:
        city = location_data.get("city") or "Unknown"
        location = (
            db.query(Location)
            .filter(Location.city == city, Location.country == location_data["country"])
            .one_or_none()
        )
        if location is None:
            location = Location(
                city=city,
                country=location_data["country"] or "Unknown",
                region=location_data.get("region"),
            )
            db.add(location)
            db.flush()

    industry_name = _detect_industry(stripped)
    industry = None
    if industry_name:
        from app.models import Industry

        industry = db.query(Industry).filter(Industry.name == industry_name).one_or_none()

    candidate = Candidate(
        full_name=name,
        headline=headline,
        seniority=title_info.get("seniority"),
        years_experience=_estimate_years(stripped),
        summary="Ingested resume (demo) — parsed deterministically from pasted text.",
        resume_text=stripped[:20000],
        location_id=location.id if location else None,
        industry_id=industry.id if industry else None,
        is_synthetic=False,
        source="ingested",
    )
    db.add(candidate)
    db.flush()

    # experience: one role derived from the headline + first "at Company" mention
    company_match = _AT_COMPANY_RE.search(stripped)
    company = None
    if company_match:
        company_name = company_match.group(1).strip()
        company = db.query(Company).filter(Company.name == company_name).one_or_none()
        if company is None:
            company = Company(name=company_name[:160])
            db.add(company)
            db.flush()
    db.add(
        Experience(
            candidate_id=candidate.id,
            title=headline or name,
            normalized_title=title_info.get("normalized_title"),
            company_id=company.id if company else None,
            is_current=True,
            sort_order=0,
        )
    )

    for match in extraction:
        normalized = (
            db.query(NormalizedSkill)
            .filter(NormalizedSkill.canonical_name == match["canonical"])
            .one_or_none()
        )
        db.add(
            Skill(
                candidate_id=candidate.id,
                name_raw=match["matched_alias"],
                normalized_skill_id=normalized.id if normalized else None,
                category=normalized.category if normalized else None,
                evidence=match["evidence"],
            )
        )
    db.flush()

    degree_match = re.search(r"\b(BSc|MSc|BA|MA|MBA|PhD)\b[^\n]{0,120}", stripped)
    if degree_match:
        db.add(
            Education(
                candidate_id=candidate.id,
                degree=degree_match.group(0)[:160],
                institution="—",
                year=None,
            )
        )

    candidate.search_text = build_search_text(
        candidate, [skill.name_raw for skill in candidate.skills]
    )
    db.flush()
    index_candidate(db, candidate, force=True)
    db.commit()
    return candidate
