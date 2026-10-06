"""API integration tests via TestClient (seeded 60-profile dataset)."""

from __future__ import annotations


class TestHealth:
    def test_health_reports_live_state(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        # ingest tests legitimately grow the shared dataset — assert floor + invariants
        assert body["counts"]["candidates"] >= 60
        assert body["counts"]["embeddings"] == body["counts"]["candidates"]
        assert body["ai"]["mode"] == "demo"
        assert body["ai"]["embedding"]["provider"].startswith("demo")
        expected_vector = (
            "pgvector" if body["database"]["dialect"] == "postgresql" else "python-cosine"
        )
        assert body["retrieval"]["vector_backend"] == expected_vector


class TestSearchEndpoints:
    def test_search_ok(self, client):
        response = client.post(
            "/api/v1/search",
            json={"query": "python backend engineer", "limit": 5},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["results"]
        assert body["parsed"]["skills"]
        assert body["query_id"] is not None

    def test_search_validation(self, client):
        assert client.post("/api/v1/search", json={"query": "x"}).status_code == 422
        assert (
            client.post(
                "/api/v1/search", json={"query": "ok query", "strategy": "nonsense"}
            ).status_code
            == 422
        )

    def test_recent_and_snapshot(self, client):
        created = client.post("/api/v1/search", json={"query": "kubernetes engineer"}).json()
        recent = client.get("/api/v1/search/recent?limit=5").json()
        assert recent
        assert recent[0]["id"] == created["query_id"]
        snapshot = client.get(f"/api/v1/search/queries/{created['query_id']}")
        assert snapshot.status_code == 200
        assert snapshot.json()["results"]

    def test_snapshot_404(self, client):
        assert client.get("/api/v1/search/queries/999999").status_code == 404


class TestCandidateEndpoints:
    def test_list_and_detail(self, client):
        listing = client.get("/api/v1/candidates?limit=5")
        assert listing.status_code == 200
        items = listing.json()
        assert len(items) == 5
        assert int(listing.headers["X-Total-Count"]) >= 60
        detail = client.get(f"/api/v1/candidates/{items[0]['id']}")
        assert detail.status_code == 200
        body = detail.json()
        assert body["skills"]
        assert body["embedding"]["model"].startswith("demo")

    def test_detail_404(self, client):
        assert client.get("/api/v1/candidates/999999").status_code == 404

    def test_ingest_roundtrip(self, client):
        resume = (
            "Lina Haddad\nStaff Machine Learning Engineer\n\n"
            "12 years of experience shipping NLP and LLM systems with PyTorch and RAG.\n"
            "Built embeddings pipelines and vector database infrastructure on AWS.\n"
            "Based in Dubai, United Arab Emirates.\n"
        )
        response = client.post("/api/v1/candidates/ingest", json={"resume_text": resume})
        assert response.status_code == 201
        body = response.json()
        assert body["full_name"] == "Lina Haddad"
        assert body["seniority"] == "staff"
        assert body["location"] == "Dubai, United Arab Emirates"
        assert body["skills_detected"] >= 4

        found = client.post("/api/v1/search", json={"query": "Lina Haddad LLM"}).json()
        assert any(item["full_name"] == "Lina Haddad" for item in found["results"][:5])

    def test_ingest_too_short(self, client):
        assert (
            client.post("/api/v1/candidates/ingest", json={"resume_text": "hi"}).status_code == 422
        )

    def test_ingest_without_skills_fails_loudly(self, client):
        response = client.post(
            "/api/v1/candidates/ingest",
            json={"resume_text": "John Doe\nProfessional napper and coffee enthusiast.\n"},
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "ingestion_failed"


class TestSavedSearches:
    def test_crud_and_run(self, client):
        created = client.post(
            "/api/v1/saved-searches",
            json={
                "name": "Berlin backend",
                "query": {"raw": "backend engineer Berlin", "strategy": "hybrid", "rerank": True},
            },
        )
        assert created.status_code == 201
        saved_id = created.json()["id"]

        listing = client.get("/api/v1/saved-searches").json()
        assert any(item["id"] == saved_id for item in listing)

        run = client.post(f"/api/v1/saved-searches/{saved_id}/run")
        assert run.status_code == 200
        body = run.json()
        assert body["saved_search"]["run_count"] == 1
        assert body["results"]

        assert client.delete(f"/api/v1/saved-searches/{saved_id}").status_code == 204
        assert client.post(f"/api/v1/saved-searches/{saved_id}/run").status_code == 404


class TestRediscovery:
    def test_jd_roundtrip(self, client):
        response = client.post(
            "/api/v1/rediscovery",
            json={
                "jd_text": (
                    "Senior Backend Engineer (5+ years) to build Python/FastAPI services "
                    "for a Dubai logistics platform with PostgreSQL, Redis, Docker and Kubernetes."
                ),
                "title": "Senior Backend Engineer",
                "company_name": "Example Freight Co",
                "limit": 5,
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert "python" in body["parsed_jd"]["skills"]
        assert "kubernetes" in body["parsed_jd"]["skills"]
        assert body["parsed_jd"]["min_years"] == 5.0
        assert body["matches"]
        assert set(body["gaps"]) <= set(body["parsed_jd"]["skills"])

        job = client.get(f"/api/v1/rediscovery/jobs/{body['job']['id']}")
        assert job.status_code == 200
        assert job.json()["title"] == "Senior Backend Engineer"

    def test_jd_validation(self, client):
        assert client.post("/api/v1/rediscovery", json={"jd_text": "too short"}).status_code == 422


class TestEvaluationEndpoints:
    def test_live_benchmark_then_persist(self, client):
        live = client.get("/api/v1/evaluation/benchmark")
        assert live.status_code == 200
        body = live.json()
        assert body["dataset_size"] >= 60
        # may be a live-computed run (4 strategies) or a stored one from an
        # earlier test — either way metrics must be present and sane
        assert set(body["strategies"]) <= {"lexical", "vector", "hybrid", "hybrid_rerank"}
        assert body["metrics"]
        for strategy_metrics in body["metrics"].values():
            for value in strategy_metrics.values():
                assert 0.0 <= value <= 1.0

        persisted = client.post(
            "/api/v1/evaluation/run",
            json={"k": 5, "strategies": ["lexical", "hybrid_rerank"]},
        )
        assert persisted.status_code == 201
        run = persisted.json()
        assert set(run["metrics"]) == {"lexical", "hybrid_rerank"}
        assert run["benchmark_run_id"]

        again = client.get("/api/v1/evaluation/benchmark").json()
        assert again["id"] == run["benchmark_run_id"]  # stored run served
