"""Reranker tests — geography multipliers, years fit, transparency."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Candidate, Skill
from app.services.fusion import FusedHit
from app.services.rerank import GEO_FACTORS, rerank


def _load(db, ids: list[int]) -> dict:
    rows = db.scalars(
        select(Candidate)
        .where(Candidate.id.in_(ids))
        .options(
            selectinload(Candidate.skills).selectinload(Skill.normalized_skill),
            joinedload(Candidate.location),
        )
    ).all()
    return {row.id: row for row in rows}


class TestRerank:
    def test_geography_multiplier_city(self, db):
        berlin = db.scalars(
            select(Candidate)
            .join(Candidate.location)
            .where(Candidate.location.has(city="Berlin"))
            .limit(1)
        ).first()
        assert berlin is not None
        other = db.scalars(select(Candidate).where(Candidate.id != berlin.id).limit(1)).first()

        fused = [
            FusedHit(candidate_id=berlin.id, score=1.0),
            FusedHit(candidate_id=other.id, score=1.0),
        ]
        candidates = _load(db, [berlin.id, other.id])
        reranked = rerank(
            fused,
            candidates,
            {berlin.id: 1.0, other.id: 1.0},
            query_family=None,
            query_skills=[],
            min_years=None,
            max_years=None,
            cities=["Berlin"],
            top_n=10,
        )
        by_id = {hit.candidate_id: hit for hit in reranked}
        assert by_id[berlin.id].components["geo_factor"] == GEO_FACTORS["city"]
        assert by_id[other.id].components["geo_factor"] == 1.0
        assert any("geo boost" in note for note in by_id[berlin.id].notes)
        assert any("outside the requested geography" in note for note in by_id[other.id].notes)

    def test_region_scope_equal_to_country(self, db):
        mena = db.scalars(
            select(Candidate)
            .join(Candidate.location)
            .where(Candidate.location.has(region="MENA"))
            .limit(1)
        ).first()
        assert mena is not None
        fused = [FusedHit(candidate_id=mena.id, score=1.0)]
        candidates = _load(db, [mena.id])
        reranked = rerank(
            fused,
            candidates,
            {mena.id: 1.0},
            query_family=None,
            query_skills=[],
            min_years=None,
            max_years=None,
            region="MENA",
            top_n=5,
        )
        assert reranked[0].components["geo_factor"] == GEO_FACTORS["region"]

    def test_years_below_minimum_penalized(self, db):
        young = db.scalars(select(Candidate).where(Candidate.years_experience < 3).limit(1)).first()
        assert young is not None
        fused = [FusedHit(candidate_id=young.id, score=1.0)]
        reranked = rerank(
            fused,
            _load(db, [young.id]),
            {young.id: 1.0},
            query_family=None,
            query_skills=[],
            min_years=10.0,
            max_years=None,
            top_n=5,
        )
        assert reranked[0].components["years_fit"] < 1.0
        assert any("below the 10" in note for note in reranked[0].notes)

    def test_family_match_note(self, db):
        backend = db.scalars(
            select(Candidate).where(Candidate.headline.ilike("%backend%")).limit(1)
        ).first()
        assert backend is not None
        reranked = rerank(
            [FusedHit(candidate_id=backend.id, score=1.0)],
            _load(db, [backend.id]),
            {backend.id: 1.0},
            query_family="backend engineer",
            query_skills=[],
            min_years=None,
            max_years=None,
            top_n=5,
        )
        assert reranked[0].components["title_family"] == 1.0
        assert any("backend engineer" in note for note in reranked[0].notes)

    def test_deterministic(self, db):
        ids = [c.id for c in db.scalars(select(Candidate).limit(5)).all()]
        fused = [FusedHit(candidate_id=i, score=1.0 / (index + 1)) for index, i in enumerate(ids)]
        candidates = _load(db, ids)
        normalized = {i: 1.0 - index * 0.1 for index, i in enumerate(ids)}
        first = rerank(
            fused,
            candidates,
            normalized,
            query_family=None,
            query_skills=[],
            min_years=None,
            max_years=None,
            top_n=5,
        )
        second = rerank(
            fused,
            candidates,
            normalized,
            query_family=None,
            query_skills=[],
            min_years=None,
            max_years=None,
            top_n=5,
        )
        assert [(hit.candidate_id, hit.score) for hit in first] == [
            (hit.candidate_id, hit.score) for hit in second
        ]
