"""Lexical retrieval tests (SQLite BM25 path)."""

from __future__ import annotations

from app.services.lexical import LexicalSearcher


class TestBM25Path:
    def test_finds_candidates_by_skill_term(self, db):
        hits = LexicalSearcher(db).search("kubernetes", None, limit=20)
        assert hits, "expected lexical hits for kubernetes"
        assert all(hit.score > 0 for hit in hits)

    def test_scores_are_ordered(self, db):
        hits = LexicalSearcher(db).search("python backend", None, limit=20)
        scores = [hit.score for hit in hits]
        assert scores == sorted(scores, reverse=True)

    def test_matched_terms_and_snippet(self, db):
        hits = LexicalSearcher(db).search("kubernetes", None, limit=5)
        top = hits[0]
        assert "kubernetes" in [term.lower() for term in top.matched_terms]
        assert top.snippet  # non-empty evidence snippet
        assert "«" in top.snippet or "kubernetes" in top.snippet.lower()

    def test_id_restriction(self, db):
        unrestricted = LexicalSearcher(db).search("python", None, limit=50)
        allowed = [hit.candidate_id for hit in unrestricted[:3]]
        restricted = LexicalSearcher(db).search("python", allowed, limit=50)
        assert {hit.candidate_id for hit in restricted} <= set(allowed)
        assert restricted, "expected hits within the restricted set"

    def test_no_hits_for_nonsense(self, db):
        assert LexicalSearcher(db).search("zzzqqqxx", None, limit=10) == []

    def test_empty_query(self, db):
        assert LexicalSearcher(db).search("   ", None, limit=10) == []
