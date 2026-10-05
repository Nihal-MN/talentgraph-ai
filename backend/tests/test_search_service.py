"""Search orchestration tests — the full pipeline on the seeded dataset."""

from __future__ import annotations

from sqlalchemy import func, select

from app.models import SearchQuery, SearchResult
from app.services.search_service import SearchRequest, run_search


def _count_searches(db) -> int:
    return db.scalar(select(func.count()).select_from(SearchQuery)) or 0


class TestHybridSearch:
    def test_demo_query_finds_berlin_backend(self, db):
        outcome = run_search(
            db,
            SearchRequest(
                raw_query="senior python backend engineer in Berlin with kubernetes experience",
                strategy="hybrid",
                limit=10,
                rerank=True,
                log=False,
            ),
        )
        assert outcome["results"]
        top3 = outcome["results"][:3]
        assert any((item["location"] or "").startswith("Berlin") for item in top3), [
            item["location"] for item in top3
        ]

    def test_parsed_signals_and_soft_semantics(self, db):
        outcome = run_search(
            db,
            SearchRequest(
                raw_query="senior python backend engineer in Berlin with kubernetes",
                limit=5,
                log=False,
            ),
        )
        parsed = outcome["parsed"]
        assert "python" in parsed["skills"] and "kubernetes" in parsed["skills"]
        assert parsed["seniority"] == ["senior"]
        assert parsed["city"] == "Berlin"
        assert outcome["filters_used"] == {}  # nothing hard-filtered from NL
        assert outcome["soft_signals"]["skills"]  # signals present
        top = outcome["results"][0]
        assert top["why"]["signals_matched"]

    def test_gulf_region_ranking(self, db):
        outcome = run_search(
            db,
            SearchRequest(raw_query="technical recruiter in the Gulf", limit=5, log=False),
        )
        assert outcome["results"]
        top5 = outcome["results"][:5]
        assert any((item["region"] or "") == "MENA" for item in top5), [
            (item["full_name"], item["location"]) for item in top5
        ]

    def test_every_result_is_explainable(self, db):
        outcome = run_search(
            db,
            SearchRequest(raw_query="data engineer with spark and airflow", limit=5, log=False),
        )
        for item in outcome["results"]:
            why = item["why"]
            has_evidence = bool(
                why["matched_skills"] or why["related_skills"] or why["text_terms_matched"]
            )
            assert has_evidence, f"no evidence for {item['full_name']}"
            assert item["components"]["fusion"]["score"] > 0

    def test_deterministic_order(self, db):
        first = run_search(db, SearchRequest(raw_query="kubernetes engineer", limit=10, log=False))
        second = run_search(db, SearchRequest(raw_query="kubernetes engineer", limit=10, log=False))
        assert [item["id"] for item in first["results"]] == [
            item["id"] for item in second["results"]
        ]


class TestHardFilters:
    def test_city_filter_is_strict(self, db):
        outcome = run_search(
            db,
            SearchRequest(
                raw_query="backend engineer",
                filters={"cities": ["Berlin"]},
                limit=20,
                log=False,
            ),
        )
        assert outcome["results"]
        assert all((item["location"] or "").startswith("Berlin") for item in outcome["results"])

    def test_skill_filter_is_strict(self, db):
        from app.services.search_service import candidate_ids_for_filters

        allowed = set(candidate_ids_for_filters(db, {"skills": ["python"]}) or [])
        outcome = run_search(
            db,
            SearchRequest(
                raw_query="engineer",
                filters={"skills": ["python"]},
                limit=20,
                log=False,
            ),
        )
        assert outcome["results"]
        assert {item["id"] for item in outcome["results"]} <= allowed

    def test_empty_filter_result_is_graceful(self, db):
        outcome = run_search(
            db,
            SearchRequest(
                raw_query="anything",
                filters={"skills": ["nonexistent-skill-xyz"]},
                limit=10,
                log=False,
            ),
        )
        assert outcome["results"] == []
        assert outcome["total"] == 0


class TestStrategyVariants:
    def test_vector_finds_synonym_documents(self, db):
        outcome = run_search(
            db,
            SearchRequest(raw_query="postgres database", strategy="vector", limit=10, log=False),
        )
        assert outcome["results"]
        canonicals = [
            skill["skill"]
            for item in outcome["results"][:5]
            for skill in item["why"]["matched_skills"] + item["why"]["related_skills"]
        ]
        assert "postgresql" in canonicals

    def test_lexical_matches_raw_alias(self, db):
        # the generator keeps "K8s" as a raw display alias in some profiles
        outcome = run_search(
            db, SearchRequest(raw_query="k8s", strategy="lexical", limit=10, log=False)
        )
        assert outcome["results"]
        assert any(
            "kubernetes" in [skill["skill"] for skill in item["why"]["matched_skills"]]
            for item in outcome["results"][:10]
        )


class TestLogging:
    def test_search_logged_by_default(self, db):
        before = _count_searches(db)
        outcome = run_search(db, SearchRequest(raw_query="logged search test", limit=5))
        assert outcome["query_id"] is not None
        assert _count_searches(db) == before + 1
        results = db.scalars(
            select(SearchResult).where(SearchResult.search_query_id == outcome["query_id"])
        ).all()
        assert len(results) == len(outcome["results"])

    def test_log_false_writes_nothing(self, db):
        before = _count_searches(db)
        run_search(db, SearchRequest(raw_query="unlogged", limit=5, log=False))
        assert _count_searches(db) == before
