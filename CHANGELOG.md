# Changelog

All notable changes are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-10-05

Initial public release: a semantic talent search and candidate rediscovery
engine with measured retrieval quality.

### Added

- **Hybrid retrieval pipeline**: natural-language parsing → soft/hard
  constraint split → candidate set → lexical retrieval (PostgreSQL FTS or
  SQLite BM25) + vector retrieval (pgvector cosine or Python fallback) →
  RRF fusion → transparent feature reranker with geography multipliers.
- **Explainable results**: every result carries a "Why this result?" panel —
  matched skills with source quotes, related skills, matched terms, snippet,
  per-strategy ranks/scores, reranker notes, and satisfied query signals.
- **Deterministic synthetic dataset**: 200 fictional profiles across 16 role
  archetypes, 260+ companies, weighted global city pool, display-alias
  variety ("K8s", "Postgres", "React.js"), coverage pins for demo-critical
  combinations, plus a deliberate prompt-injection fixture.
- **Skill taxonomy & normalization**: ~150 canonical skills with aliases,
  categories and a related-skill graph; title seniority/family detection;
  earliest-mention location resolution; years parsing.
- **Keyless demo embeddings** (deterministic lexical-semantic feature
  hashing) with an OpenAI embeddings adapter behind the same interface.
- **Evaluation harness**: 24-query golden set with ground-truth graded
  labels; P@K / R@K / MRR / nDCG; benchmark runner comparing 4 strategies;
  persisted runs powering the Evaluation page.
- **Resume ingestion**: paste text → structured profile (skills with
  evidence, title, seniority, location, years) → embedded and searchable.
- **Talent rediscovery**: paste a JD → parsed requirements, pool matches,
  explicit gaps, save-as-search.
- **Saved searches** with one-click re-runs, search analytics logging.
- **Six-page web UI** (Next.js): search + filters, candidate profile,
  saved searches, evaluation dashboard, rediscovery, system health.
- **Docker-first DX**: `docker compose up --build -d` seeds on first boot;
  PostgreSQL + pgvector, API and web containers with health checks.
- **Test suite**: hermetic SQLite suite + PostgreSQL/pgvector CI job, a
  20-eval named retrieval suite, frontend tests, and Docker builds — all on
  GitHub Actions.

### Notes

- Local demo posture: no authentication by design; synthetic data only.
- Live OpenAI paths (embeddings, LLM parsing) are adapter-complete and
  stub-tested; run with `AI_PROVIDER` + `OPENAI_API_KEY` to exercise them.
