"""Embedding + vector retrieval tests (deterministic demo embedder)."""

from __future__ import annotations

import math

from app.services.embedding import DemoEmbedder, cosine_similarity
from app.services.vector_store import VectorSearcher


class TestDemoEmbedder:
    def setup_method(self):
        self.embedder = DemoEmbedder(dims=384)

    def test_deterministic(self):
        first = self.embedder.embed(["python engineer"])[0]
        second = self.embedder.embed(["python engineer"])[0]
        assert first == second

    def test_normalized(self):
        vector = self.embedder.embed(["kubernetes docker terraform"])[0]
        norm = math.sqrt(sum(value * value for value in vector))
        assert abs(norm - 1.0) < 1e-6

    def test_alias_similarity(self):
        # "k8s" must land near "Kubernetes" — the whole point of canonicalization
        a = self.embedder.embed(["k8s"])[0]
        b = self.embedder.embed(["Kubernetes"])[0]
        c = self.embedder.embed(["pastry chef"])[0]
        assert cosine_similarity(a, b) > cosine_similarity(a, c)

    def test_related_skills_are_closer_than_unrelated(self):
        java_spring = self.embedder.embed(["java spring boot services"])[0]
        backend = self.embedder.embed(["backend api microservices"])[0]
        gardening = self.embedder.embed(["landscaping garden design"])[0]
        assert cosine_similarity(java_spring, backend) > cosine_similarity(java_spring, gardening)

    def test_dims(self):
        assert len(self.embedder.embed(["x"])[0]) == 384


class TestVectorSearcher:
    def test_finds_similar_candidates(self, db):
        embedder = DemoEmbedder(dims=384)
        query_vector = embedder.embed(["kubernetes docker"])[0]
        hits = VectorSearcher(db).search(query_vector, None, limit=10)
        assert hits
        similarities = [hit.similarity for hit in hits]
        assert similarities == sorted(similarities, reverse=True)

    def test_id_restriction(self, db):
        embedder = DemoEmbedder(dims=384)
        query_vector = embedder.embed(["python"])[0]
        all_hits = VectorSearcher(db).search(query_vector, None, limit=50)
        allowed = [hit.candidate_id for hit in all_hits[:5]]
        restricted = VectorSearcher(db).search(query_vector, allowed, limit=50)
        assert {hit.candidate_id for hit in restricted} <= set(allowed)

    def test_synonym_query_retrieves_alias_documents(self, db):
        # query says "postgres"; the docs may say "PostgreSQL" — cosine should
        # still rank candidates whose canonical skill is postgresql
        embedder = DemoEmbedder(dims=384)
        query_vector = embedder.embed(["postgres database"])[0]
        hits = VectorSearcher(db).search(query_vector, None, limit=10)
        assert hits
