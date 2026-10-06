# Evaluation — what we measure, and what the numbers honestly mean

TalentGraph compares four retrieval strategies on a fixed golden set and
reports textbook IR metrics. This page documents exactly how, so the numbers
can be trusted — and their limits stated plainly.

## The golden set

- **24 queries** (`backend/app/evaluation/golden.py`): exact-skill queries,
  synonym/alias queries, location and region asks, seniority/years asks,
  domain (fintech/healthtech) asks, and four deliberately *diffuse*
  paraphrase queries with no hard constraints.
- **Ground truth by construction**: the synthetic generator knows every
  profile's skills, seniority, years, city, country, region and industry, so
  each query carries a deterministic predicate. Grades: **2 = ideal,
  1 = acceptable, 0 = irrelevant**.
- This is honest by design: it measures **retrieval mechanics**
  (exactness, synonym handling, filter correctness, fusion quality)
  **reproducibly**. It is not a claim about human relevance judgment — a
  production system would calibrate labels from recruiter click/save data.

## Metrics (standard definitions)

| Metric | Definition |
|---|---|
| Precision@K | share of the top K that is relevant (grade > 0), divided by K |
| Recall@K | share of all relevant profiles found in the top K |
| MRR | 1 / rank of the first relevant result |
| nDCG@K | graded gain `(2^g − 1)/log2(i+1)` normalized by the ideal ordering |

The runner executes the **real pipeline** (parse → soft/hard split →
retrieval → fusion → rerank) per query per strategy, with k = 10:
`lexical`, `vector`, `hybrid`, `hybrid_rerank`. Results are persisted
(`benchmark_runs`) and shown on the Evaluation page.

## What the numbers show (200-profile dataset, demo embedder)

Measured on the seeded dataset **on the docker stack (PostgreSQL + pgvector)**
— the default path, and exactly what the Evaluation page displays after
`docker compose up`. `make bench` reproduces + persists them:

| Strategy | P@10 | R@10 | MRR | nDCG@10 |
|---|---|---|---|---|
| Lexical only | 0.696 | 0.429 | 0.852 | 0.685 |
| Vector only | 0.663 | 0.409 | 0.804 | 0.557 |
| Hybrid (RRF) | 0.758 | 0.475 | **0.938** | 0.724 |
| Hybrid + rerank | **0.779** | **0.492** | **0.958** | **0.785** |

The hermetic SQLite fallback (BM25 + Python cosine) produces slightly
different numbers at the lexical layer — lexical P@10 is 0.746 there versus
0.696 on PostgreSQL FTS. Both are real; cross-backend comparisons should use
ranks (which is what RRF consumes), never absolute scores.

Reading: lexical is strong when queries share exact terms; the vector path
catches alias/paraphrase matches that never co-occur literally ("k8s" ↔
"Kubernetes", "postgres" ↔ "PostgreSQL"); fusion wins or ties on most metrics
(its MRR lift is the "always-good-first-hit" property of rank fusion); the
transparent reranker adds the skill/experience/geography layer on top.

## Design decision: soft constraints vs hard filters

Natural-language constraints ("5+ years", "in Berlin", "senior") are **soft
ranking signals**: they steer the reranker and appear per-result in the
"Why" panel — but they do not shrink the candidate set. Only *explicit*
filters (the filter panel / API `filters`) become hard SQL constraints.

Why: early testing hard-filtered every parsed constraint and collapsed
candidate pools to 1–11 rows per query — below any ranking window — making
every strategy tie and metrics meaningless. Real recruiters also treat
"Berlin" as a preference to weigh against a great match, not an automatic
in/out. Explicitness keeps filtering predictable: what you type in the
filter panel is exactly what filters.

## Known limits (stated, not hidden)

- The demo embedder is lexical-semantic, **not a neural model** — it will
  not capture deep paraphrase ("scaled payment rails" ≈ "payments
  infrastructure") the way a trained encoder would. The OpenAI embeddings
  adapter is the production path for that; switching re-embeds via
  `make reembed`.
- Labels are synthetic predicates, not human judgments (see above).
- Metrics are computed at k=10 on a 200-profile pool; on much larger pools
  recall@10 would naturally drop while trends hold.
- Lexical on PostgreSQL uses FTS ranking (`ts_rank_cd`); the SQLite fallback
  uses BM25 — both are "lexical", but absolute scores aren't comparable
  across backends (ranks are, which is what RRF consumes).

## Reproducing

```bash
make bench          # compute + persist the benchmark from the CLI
make eval           # the named eval suite (behavioral checks, pytest)
# or: docker compose exec api python scripts/run_benchmark.py --persist
```

The dataset is deterministic (seed=42), so numbers are stable run to run.
