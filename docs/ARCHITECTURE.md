# Architecture

TalentGraph AI is a **modular monolith**: one FastAPI service holds the domain
model, the retrieval pipeline and the evaluation harness; one Next.js app is
the recruiter-facing UI; PostgreSQL (with pgvector) is the store. Nothing
talks to an LLM unless you configure a key.

## System view

```
┌─────────────────────┐        ┌──────────────────────────────────────────┐
│  Next.js web (3400) │  HTTP  │  FastAPI api (8300)                      │
│  search / why /     │ ─────▶ │                                          │
│  rediscovery / eval │        │  parse → filter → retrieve → fuse →      │
└─────────────────────┘        │  rerank → evidence → log                 │
                               │                                          │
                               │  lexical: PG FTS / BM25   ┐              │
                               │  vector:  pgvector / cos  ├─ adapters    │
                               │  embed:   demo / OpenAI   ┘              │
                               └──────────────────┬───────────────────────┘
                                                  │ SQLAlchemy 2
                                        ┌─────────▼──────────┐
                                        │ PostgreSQL+pgvector│
                                        │ (SQLite dev fallback)
                                        └────────────────────┘
```

## The retrieval pipeline (one path, used by everything)

1. **Parse** — natural language → structured intent (skills, seniority,
   years, city/country/region, title family, industry, free-text remainder,
   related-skill expansions). Rule-based parser is the default and needs no
   key; an LLM parser adapter produces the same structure when configured.
2. **Soft/hard split** — constraints *written in prose* are soft ranking
   signals; constraints *explicitly set as filters* (UI panel / API) are hard
   SQL constraints. Rationale in `docs/EVALUATION.md`.
3. **Candidate set** — hard filters compile to a SQL restriction (skills via
   the normalized-skill table, years, seniority, city/country/region,
   industry, title family via normalized keywords).
4. **Lexical retrieval** — PostgreSQL full-text search (`tsvector`,
   `websearch_to_tsquery`, `ts_rank_cd`, `ts_headline` snippets) or Okapi
   BM25 computed in Python on the SQLite dev fallback. Same interface both
   ways.
5. **Vector retrieval** — embeddings via a provider adapter:
   - `demo` (default, keyless): a deterministic feature-hashed
     *lexical-semantic* embedder. Tokens are canonicalized through the skill
     taxonomy ("k8s" → kubernetes, "Postgres" → postgresql) and expanded with
     the taxonomy's related-skill graph before hashing — so semantic
     neighbors genuinely score close, and identical inputs always produce
     identical vectors.
   - `openai` (when `OPENAI_API_KEY` is set): `text-embedding-3-small` behind
     the same interface.
   Storage: native `vector(384)` column with a cosine (`<=>`) query and HNSW
   index on PostgreSQL; JSON column + Python cosine on SQLite.
6. **Fusion** — Reciprocal Rank Fusion, `Σ 1/(k + rank)` with `k=60`.
   RRF needs no score calibration between the two spaces (ADRs 0001/0002).
7. **Rerank** (toggleable) — transparent feature stage:
   `0.55·fusion + 0.17·title-family + 0.15·skill-overlap + 0.13·years-fit`,
   multiplied by a geography factor (exact city ×1.40, country/region ×1.35).
   Every component emits a human-readable note.
8. **Evidence ("Why this result")** — matched skills with their source
   quotes, related skills, matched query terms, a highlighted snippet,
   per-strategy ranks/scores, reranker notes, and which query signals the
   candidate satisfies.
9. **Log** — every search is persisted (`search_queries` + top-20
   `search_results` snapshots) — the analytics and snapshot endpoints read
   from here. The benchmark runs the identical pipeline with logging off.

## Domain model (13 core entities)

| Entity | Purpose |
|---|---|
| Candidate | profile root: headline, seniority, years, summary, resume text, search text |
| Experience | roles with normalized titles and date ranges |
| Skill | raw skill mentions with **evidence quotes** + link to canonical skill |
| NormalizedSkill | canonical skills: category, aliases, related-skill graph |
| Education | degrees and institutions |
| Company | fictional companies with industry + HQ |
| Industry | canonical industry list |
| Location | city / country / region |
| EmbeddingMetadata | model, dims, content hash, vector, embedded-at |
| SearchQuery | search log: raw text, parsed intent, strategy, latency, counts |
| SearchResult | per-search snapshot rows with full score components |
| SavedSearch | named searches for one-click re-runs |
| Job | pasted JD + parsed requirements (rediscovery) |

Operational extra: `benchmark_runs` stores evaluation runs for the UI.

## The dataset

`python -m app.seed` builds a **deterministic synthetic dataset** (seed=42,
`--count` configurable, default 200): 16 role archetypes × seniority mix ×
weighted city pool, 260+ fictional companies, skills drawn from the taxonomy
with display aliases ("K8s", "Postgres", "React.js") — plus a few coverage
pins that guarantee demo-critical combinations (a senior Python/Kubernetes
backend engineer in Berlin, a Dubai recruiter). One profile deliberately
carries a prompt-injection payload as test data. All of it is fabricated;
emails are `@example.com`-style, phones are 555 ranges. Nothing is scraped.

## Where things live

```
backend/app/
  core/        settings + error model
  db/          engine/session + portable vector column type
  models/      the 13 entities
  services/    taxonomy, normalize, embedding, lexical, vector_store,
               fusion, rerank, query_parser, search_service, ingestion,
               indexing
  evaluation/  metrics, golden set, benchmark runner
  api/         routes (search, candidates, saved, rediscovery, evaluation, health)
frontend/src/
  app/         the six pages
  components/  AppShell, ui kit, FiltersPanel, SearchResultCard (the Why panel)
  lib/         typed API client + formatters
```
