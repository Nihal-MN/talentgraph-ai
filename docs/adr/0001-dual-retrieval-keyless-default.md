# ADR 0001 — Dual retrieval with pluggable adapters (keyless by default)

**Status:** accepted

**Context.** Recruiters search with synonyms, abbreviations and paraphrases
("k8s", "postgres", "worked on payment rails") that literal keyword search
misses. A semantic layer fixes that, but requiring an API key to boot a demo
is a terrible first-run experience, and an unverifiable "trust me, it's AI"
embedding is worse.

**Decision.** Two retrieval paths behind one interface each:
- lexical: PostgreSQL FTS (prod) / BM25 (dev fallback)
- vector: pgvector (prod) / Python cosine (dev fallback)
with embeddings behind a provider adapter: a **deterministic, feature-hashed
lexical-semantic embedder** (taxonomy-canonicalized tokens + related-skill
expansion) as the keyless default, and OpenAI `text-embedding-3-small` behind
the same interface when a key is configured. Ranking quality is measured
either way by the golden-set benchmark.

**Consequences.** The whole product works offline, deterministically, and the
demo embedder's behavior is explainable (canonicalization + expansion, not a
black box). Deep paraphrase quality needs the live adapter; the README and
`docs/EVALUATION.md` say so explicitly.
