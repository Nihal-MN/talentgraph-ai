"""Deterministic feature-based reranker.

A transparent second stage on top of RRF fusion — no LLM, no hidden weights.

Base score: ``0.55·fusion + 0.17·title-family + 0.15·skill-overlap +
0.13·years fit``. Geography is applied as a *multiplier* because recruiting
geography is a scope decision: an exact city match multiplies by 1.35, a
country match by 1.25, a region match by 1.20 — so a solid regional candidate
outranks a marginally-better-matching distant one (and a Dubaian tops a
"in Dubai" search). Every component and factor emits a human-readable note
for the "Why this result" panel. Toggleable per query.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Candidate
from app.services.fusion import FusedHit
from app.services.normalize import normalize_title

WEIGHTS = {
    "fusion": 0.55,
    "title_family": 0.17,
    "skill_overlap": 0.15,
    "years_fit": 0.13,
}

# geography multiplier — an exact city is the strongest signal; an explicit
# country or region scope ("the Gulf") re-scores comparably (recruiting scope
# questions are answered regionally, not by marginal match-quality gaps).
GEO_FACTORS = {"city": 1.40, "country": 1.35, "region": 1.35}


@dataclass
class RerankedHit:
    candidate_id: int
    score: float
    notes: list[str] = field(default_factory=list)
    components: dict[str, float] = field(default_factory=dict)


def _years_fit(
    candidate: Candidate, min_years: float | None, max_years: float | None
) -> tuple[float, str | None]:
    years = candidate.years_experience
    if years is None or (min_years is None and max_years is None):
        return 0.5, None
    if min_years is not None and years < min_years:
        gap = min_years - years
        score = max(0.0, 1.0 - gap / max(min_years, 1.0))
        return score, f"{years:g} yrs — below the {min_years:g}+ the query asks for"
    if max_years is not None and years > max_years:
        gap = years - max_years
        score = max(0.0, 1.0 - gap / max(max_years, 1.0))
        return score, f"{years:g} yrs — above the {max_years:g} ceiling"
    return 1.0, f"{years:g} yrs of experience fits the range"


def rerank(
    fused: list[FusedHit],
    candidates_by_id: dict[int, Candidate],
    normalized_fusion: dict[int, float],
    *,
    query_family: str | None,
    query_skills: list[str],
    min_years: float | None,
    max_years: float | None,
    countries: list[str] | None = None,
    cities: list[str] | None = None,
    region: str | None = None,
    top_n: int = 20,
) -> list[RerankedHit]:
    countries = [country.lower() for country in (countries or [])]
    cities = [city.lower() for city in (cities or [])]
    results: list[RerankedHit] = []

    for hit in fused[: max(top_n * 3, 60)]:
        candidate = candidates_by_id.get(hit.candidate_id)
        if candidate is None:
            continue
        notes: list[str] = []
        components: dict[str, float] = {}

        fusion_score = normalized_fusion.get(hit.candidate_id, 0.0)
        components["fusion"] = round(fusion_score, 4)

        # title family
        family_score = 0.0
        if query_family:
            candidate_family = normalize_title(candidate.headline or "")["family"]
            if candidate_family == query_family:
                family_score = 1.0
                notes.append(f"headline matches the “{query_family}” intent")
            elif candidate_family:
                notes.append(f"headline family is “{candidate_family}” (query: {query_family})")
        else:
            family_score = 0.5
        components["title_family"] = family_score

        # skill overlap against (expanded) query skills
        candidate_canonical = {
            (
                skill.normalized_skill.canonical_name
                if skill.normalized_skill
                else skill.name_raw.lower()
            )
            for skill in candidate.skills
        }
        if query_skills:
            overlap = len(set(query_skills) & candidate_canonical)
            ratio = overlap / len(set(query_skills))
            components["skill_overlap"] = round(ratio, 4)
            if overlap:
                matched = sorted(set(query_skills) & candidate_canonical)
                notes.append(f"skills matched: {', '.join(matched[:6])}")
        else:
            components["skill_overlap"] = 0.5

        # years fit
        years_score, years_note = _years_fit(candidate, min_years, max_years)
        components["years_fit"] = round(years_score, 4)
        if years_note:
            notes.append(years_note)

        # geography multiplier — city > country > region scope
        geo_factor = 1.0
        geo_asked = bool(cities or countries or region)
        if geo_asked:
            city = (candidate.location.city if candidate.location else "").lower()
            country = (candidate.location.country if candidate.location else "").lower()
            cand_region = candidate.location.region if candidate.location else ""
            if cities and city in cities:
                geo_factor = GEO_FACTORS["city"]
                notes.append(
                    f"based in {candidate.location.city}, as requested "
                    f"(geo boost ×{geo_factor:.2f})"
                )
            elif countries and country in countries:
                geo_factor = GEO_FACTORS["country"]
                notes.append(
                    f"based in {candidate.location.country}, as requested "
                    f"(geo boost ×{geo_factor:.2f})"
                )
            elif region and cand_region == region:
                geo_factor = GEO_FACTORS["region"]
                notes.append(
                    f"based in {cand_region} (region), as requested (geo boost ×{geo_factor:.2f})"
                )
            else:
                notes.append("outside the requested geography")
        components["geo_factor"] = geo_factor

        base = (
            WEIGHTS["fusion"] * components["fusion"]
            + WEIGHTS["title_family"] * components["title_family"]
            + WEIGHTS["skill_overlap"] * components["skill_overlap"]
            + WEIGHTS["years_fit"] * components["years_fit"]
        )
        total = base * geo_factor
        results.append(
            RerankedHit(
                candidate_id=hit.candidate_id,
                score=round(total, 6),
                notes=notes,
                components={key: round(value, 4) for key, value in components.items()},
            )
        )

    results.sort(key=lambda item: (-item.score, item.candidate_id))
    return results[:top_n]
