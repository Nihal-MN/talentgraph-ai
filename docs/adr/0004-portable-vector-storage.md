# ADR 0004 — Portable vector storage (native pgvector, graceful fallback)

**Status:** accepted

**Context.** PostgreSQL + pgvector is the production stack and the honest
showcase (real `vector` column, cosine operator, HNSW index). But hermetic
tests and laptop dev benefit from the SQLite fallback; forcing PostgreSQL for
every test adds CI weight and flakiness.

**Decision.** A custom SQLAlchemy `VectorType` maps one model column to:
- `vector(384)` on PostgreSQL (with `<=>` cosine queries and an HNSW index
  created in the initial migration when the extension exists), and
- `TEXT` (JSON-encoded floats) elsewhere, with cosine similarity computed in
  Python for the fallback store.

Both backends implement one `VectorSearcher` interface. CI runs the full
suite twice: hermetic SQLite *and* a real `pgvector/pgvector:pg16` service —
so the native path is genuinely exercised, not assumed.

**Consequences.** One model definition, no dialect forks in the domain layer.
Characteristics that differ by backend (FTS vs BM25; native vs Python cosine)
are documented in `/health` (`vector_backend`, `lexical_backend`) and in
`docs/EVALUATION.md`; comparisons across backends use ranks, never raw scores.
