"""Search orchestration.

One pipeline used by the API, the benchmark and the rediscovery workflow:

    parse → merge filters → structured candidate set → lexical + vector
    retrieval → RRF fusion → optional rerank → evidence assembly → log

Every result carries its full evidence ("why"): per-strategy ranks/scores,
matched terms with a snippet, matched skills with quoted resume lines,
applied filters and rerank notes.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.models import (
    Candidate,
    Industry,
    Location,
    NormalizedSkill,
    SearchQuery,
    SearchResult,
    Skill,
)
from app.services.embedding import get_embedding_provider
from app.services.fusion import FusedHit, normalize_scores, reciprocal_rank_fusion
from app.services.lexical import LexicalHit, LexicalSearcher
from app.services.query_parser import ParsedQuery, get_query_parser
from app.services.rerank import rerank
from app.services.taxonomy import TITLE_FAMILIES
from app.services.vector_store import VectorHit, VectorSearcher

STRATEGIES = ("lexical", "vector", "hybrid")


@dataclass
class SearchRequest:
    raw_query: str
    filters: dict = field(default_factory=dict)  # explicit (UI/API) filters = hard constraints
    strategy: str = "hybrid"
    limit: int = 20
    rerank: bool = True
    log: bool = True
    job_id: int | None = None


def clean_filters(explicit: dict | None) -> dict:
    """Hard filters = explicitly provided constraints only."""
    return {key: value for key, value in (explicit or {}).items() if value not in (None, [], "")}


def _soft_or_hard(hard: dict, soft: dict, key: str):
    """Prefer an explicit (hard) value; fall back to the parsed soft signal."""
    value = hard.get(key)
    if value in (None, "", []):
        value = soft.get(key)
    return value


def candidate_ids_for_filters(db: Session, filters: dict) -> list[int] | None:
    """Apply structured filters; returns None when no filter is present."""
    if not filters:
        return None
    query = select(Candidate.id)

    for skill in filters.get("skills") or []:
        subquery = (
            select(Skill.candidate_id)
            .join(NormalizedSkill, Skill.normalized_skill_id == NormalizedSkill.id)
            .where(NormalizedSkill.canonical_name == str(skill).lower())
        )
        query = query.where(Candidate.id.in_(subquery))

    if filters.get("min_years") is not None:
        query = query.where(Candidate.years_experience >= filters["min_years"])
    if filters.get("max_years") is not None:
        query = query.where(Candidate.years_experience <= filters["max_years"])

    seniority = filters.get("seniority") or []
    if seniority:
        query = query.where(Candidate.seniority.in_(seniority))

    cities = filters.get("cities") or []
    countries = filters.get("countries") or []
    region = filters.get("region")
    if cities or countries or region:
        query = query.join(Location, Candidate.location_id == Location.id)
        conditions = []
        if cities:
            conditions.append(Location.city.in_(cities))
        if countries:
            conditions.append(Location.country.in_(countries))
        if region:
            conditions.append(Location.region == region)
        query = query.where(or_(*conditions))

    industry = filters.get("industry")
    if industry:
        query = query.join(Industry, Candidate.industry_id == Industry.id).where(
            Industry.name == industry
        )

    family = filters.get("family")
    if family:
        keywords = TITLE_FAMILIES.get(family, [family])
        query = query.where(
            or_(*[Candidate.headline.ilike(f"%{keyword}%") for keyword in keywords])
        )

    return list(db.scalars(query).all())


def _candidate_summary(candidate: Candidate) -> dict:
    skills = []
    for skill in candidate.skills:
        canonical = (
            skill.normalized_skill.canonical_name
            if skill.normalized_skill
            else skill.name_raw.lower()
        )
        skills.append(canonical)
    return {
        "id": candidate.id,
        "full_name": candidate.full_name,
        "headline": candidate.headline,
        "seniority": candidate.seniority,
        "years_experience": candidate.years_experience,
        "location": candidate.location.label if candidate.location else None,
        "country": candidate.location.country if candidate.location else None,
        "region": candidate.location.region if candidate.location else None,
        "industry": candidate.industry.name if candidate.industry else None,
        "skills": skills[:12],
    }


def _build_why(
    candidate: Candidate,
    parsed: ParsedQuery,
    filters: dict,
    lexical_hit: LexicalHit | None,
    rerank_notes: list[str],
) -> dict:
    wanted = {skill for skill in parsed.skills}
    wanted.update(str(skill).lower() for skill in (filters.get("skills") or []))
    sig = parsed.to_filters()
    signals_matched: list[str] = []
    min_years = sig.get("min_years")
    years = candidate.years_experience
    if min_years is not None and years is not None and years >= min_years:
        signals_matched.append(f"experience {years:g} yrs ≥ {min_years:g} requested")
    location = candidate.location
    if location is not None:
        sig_cities = sig.get("cities") or []
        sig_countries = sig.get("countries") or []
        if sig_cities and location.city in sig_cities:
            signals_matched.append(f"based in {location.city}, as requested")
        elif sig_countries and location.country in sig_countries:
            signals_matched.append(f"based in {location.country}, as requested")
        elif sig.get("region") and location.region == sig["region"]:
            signals_matched.append(f"based in {location.region}, as requested")
    sig_seniority = sig.get("seniority") or []
    if sig_seniority and candidate.seniority in sig_seniority:
        signals_matched.append(f"{candidate.seniority} level matches the request")
    sig_industry = sig.get("industry")
    if sig_industry and candidate.industry is not None and candidate.industry.name == sig_industry:
        signals_matched.append(f"{sig_industry} industry background matches")
    related = {skill for skill in parsed.expansions}

    matched_skills: list[dict] = []
    related_skills: list[dict] = []
    for skill in candidate.skills:
        canonical = (
            skill.normalized_skill.canonical_name
            if skill.normalized_skill
            else skill.name_raw.lower()
        )
        if canonical in wanted:
            matched_skills.append({"skill": canonical, "evidence": skill.evidence})
        elif canonical in related:
            related_skills.append({"skill": canonical, "evidence": skill.evidence})

    return {
        "matched_skills": matched_skills,
        "related_skills": related_skills,
        "text_terms_matched": lexical_hit.matched_terms if lexical_hit else [],
        "snippet": lexical_hit.snippet if lexical_hit else "",
        "rerank_notes": rerank_notes,
        "signals_matched": signals_matched,
        "filters_applied": filters,
    }


def run_search(db: Session, request: SearchRequest) -> dict:
    settings = get_settings()
    started = time.perf_counter()

    strategy = request.strategy if request.strategy in STRATEGIES else "hybrid"
    limit = max(1, min(request.limit or settings.default_limit, settings.max_limit))

    parser = get_query_parser()
    parsed = parser.parse(request.raw_query)

    hard_filters = clean_filters(request.filters)
    signals = parsed.to_filters()

    restricted_ids = candidate_ids_for_filters(db, hard_filters)
    empty_result = {
        "query_id": None,
        "parsed": asdict(parsed),
        "filters_used": hard_filters,
        "soft_signals": signals,
        "strategy": strategy,
        "rerank": request.rerank,
        "took_ms": 0,
        "total": 0,
        "results": [],
    }
    if restricted_ids is not None and not restricted_ids:
        if request.log:
            empty_result["query_id"] = _persist_query(
                db, request, parsed, hard_filters, [], started
            )
        empty_result["took_ms"] = int((time.perf_counter() - started) * 1000)
        return empty_result

    # ── retrieval ────────────────────────────────────────────────────────
    lexical_hits: list[LexicalHit] = []
    vector_hits: list[VectorHit] = []

    if strategy in ("lexical", "hybrid"):
        lexical_query = " ".join([*parsed.text_terms, *parsed.skills])
        if lexical_query.strip():
            lexical_hits = LexicalSearcher(db).search(lexical_query, restricted_ids, limit=50)

    if strategy in ("vector", "hybrid"):
        vector_query_text = " ".join([parsed.raw, *parsed.expansions])
        query_vector = get_embedding_provider().embed([vector_query_text])[0]
        vector_hits = VectorSearcher(db).search(query_vector, restricted_ids, limit=50)

    rankings: dict[str, list[int]] = {}
    raw_scores: dict[str, dict[int, float]] = {}
    if lexical_hits:
        rankings["lexical"] = [hit.candidate_id for hit in lexical_hits]
        raw_scores["lexical"] = {hit.candidate_id: hit.score for hit in lexical_hits}
    if vector_hits:
        rankings["vector"] = [hit.candidate_id for hit in vector_hits]
        raw_scores["vector"] = {hit.candidate_id: hit.similarity for hit in vector_hits}

    if not rankings:
        if request.log:
            empty_result["query_id"] = _persist_query(
                db, request, parsed, hard_filters, [], started
            )
        empty_result["took_ms"] = int((time.perf_counter() - started) * 1000)
        return empty_result

    fused: list[FusedHit] = reciprocal_rank_fusion(
        rankings, k=settings.rrf_k, raw_scores=raw_scores
    )
    normalized = normalize_scores(fused)

    # ── load candidates (eager relations for rerank + evidence) ─────────
    top_ids = [hit.candidate_id for hit in fused][:60]
    candidates = db.scalars(
        select(Candidate)
        .where(Candidate.id.in_(top_ids))
        .options(
            selectinload(Candidate.skills).selectinload(Skill.normalized_skill),
            joinedload(Candidate.location),
            joinedload(Candidate.industry),
        )
    ).all()
    candidates_by_id = {candidate.id: candidate for candidate in candidates}

    lexical_by_id = {hit.candidate_id: hit for hit in lexical_hits}
    vector_by_id = {hit.candidate_id: hit for hit in vector_hits}

    if request.rerank:
        reranked = rerank(
            fused,
            candidates_by_id,
            normalized,
            query_family=hard_filters.get("family") or parsed.family,
            query_skills=[*parsed.skills, *(hard_filters.get("skills") or [])],
            min_years=_soft_or_hard(hard_filters, signals, "min_years"),
            max_years=_soft_or_hard(hard_filters, signals, "max_years"),
            countries=_soft_or_hard(hard_filters, signals, "countries"),
            cities=_soft_or_hard(hard_filters, signals, "cities"),
            region=_soft_or_hard(hard_filters, signals, "region"),
            top_n=limit,
        )
        ordering = [
            (item.candidate_id, item.score, item.notes, item.components) for item in reranked
        ]
    else:
        ordering = [
            (hit.candidate_id, normalized.get(hit.candidate_id, hit.score), [], {})
            for hit in fused[:limit]
        ]

    fused_by_id = {hit.candidate_id: hit for hit in fused}
    results = []
    for position, (candidate_id, score, notes, rerank_components) in enumerate(ordering, start=1):
        candidate = candidates_by_id.get(candidate_id)
        if candidate is None:
            continue
        lexical_hit = lexical_by_id.get(candidate_id)
        vector_hit = vector_by_id.get(candidate_id)
        fused_hit = fused_by_id[candidate_id]
        components = {
            "lexical": (
                {
                    "rank": fused_hit.ranks.get("lexical"),
                    "score": round(raw_scores["lexical"].get(candidate_id, 0.0), 4),
                    "matched_terms": lexical_hit.matched_terms if lexical_hit else [],
                }
                if lexical_hit
                else None
            ),
            "vector": (
                {
                    "rank": fused_hit.ranks.get("vector"),
                    "similarity": round(raw_scores["vector"].get(candidate_id, 0.0), 4),
                }
                if vector_hit
                else None
            ),
            "fusion": {
                "score": fused_hit.score,
                "normalized": round(normalized.get(candidate_id, 0.0), 4),
            },
            "rerank": {"score": score, "components": rerank_components, "notes": notes}
            if request.rerank
            else None,
        }
        results.append(
            {
                **_candidate_summary(candidate),
                "rank": position,
                "score": round(score, 6),
                "components": components,
                "why": _build_why(candidate, parsed, hard_filters, lexical_hit, notes),
            }
        )

    took_ms = int((time.perf_counter() - started) * 1000)
    query_id = None
    if request.log:
        query_id = _persist_query(db, request, parsed, hard_filters, results, started)

    return {
        "query_id": query_id,
        "parsed": asdict(parsed),
        "filters_used": hard_filters,
        "soft_signals": signals,
        "strategy": strategy,
        "rerank": request.rerank,
        "took_ms": took_ms,
        "total": len(fused),
        "results": results,
    }


def _persist_query(
    db: Session,
    request: SearchRequest,
    parsed: ParsedQuery,
    filters: dict,
    results: list[dict],
    started: float,
) -> int:
    row = SearchQuery(
        raw_query=request.raw_query,
        parsed=asdict(parsed),
        strategy=request.strategy,
        rerank=request.rerank,
        result_count=len(results),
        latency_ms=int((time.perf_counter() - started) * 1000),
        job_id=request.job_id,
    )
    db.add(row)
    db.flush()
    for result in results[:20]:
        db.add(
            SearchResult(
                search_query_id=row.id,
                candidate_id=result["id"],
                rank=result["rank"],
                score=result["score"],
                components=result["components"],
            )
        )
    db.commit()
    return row.id
