# Portfolio & Interview Pack — TalentGraph AI

Everything you need to talk about this project confidently: resume bullets,
a LinkedIn post, a 5-minute demo script, and the interview questions this
build answers well.

---

## Résumé bullets (pick 3–4)

- Built **TalentGraph AI**, an open-source semantic talent search engine
  (Python/FastAPI, PostgreSQL+pgvector, Next.js): hybrid retrieval combining
  full-text search, embeddings and Reciprocal Rank Fusion, with a
  deterministic keyless demo mode and an OpenAI adapter.
- Designed an **explainable ranking pipeline** — every result surfaces
  matched skills *with source quotes*, per-strategy ranks and reranker
  notes — and made geography a first-class, documented scoring factor.
- Built a **measured retrieval evaluation harness**: a 24-query golden set
  with graded ground-truth labels, reporting Precision@K / Recall@K / MRR /
  nDCG across four strategies; used the numbers to make design decisions
  (documented in ADRs, including reversing an over-filtering approach).
- Shipped a **synthetic-data generator** producing 200 deterministic
  profiles (aliases like "K8s"/"Postgres", coverage pins for demo-critical
  combinations) — reproducible benchmarks with zero real-person data.
- CI runs the full suite against **both SQLite and a real pgvector service**
  plus Docker image builds; 110 backend tests + 20 named retrieval evals +
  frontend tests, all green on GitHub Actions.

## LinkedIn post (draft)

> I built an open-source **semantic talent search engine** — the kind of
> search recruiters actually want, where "senior Python backend engineer in
> Berlin with Kubernetes experience" just… works.
>
> Under the hood: hybrid retrieval (PostgreSQL full-text + pgvector
> embeddings combined with Reciprocal Rank Fusion), a transparent reranker,
> and — my favorite part — **every result explains itself**: which resume
> lines matched, lexical rank, cosine similarity, fusion score, and the
> geography boost, line by line.
>
> The part I'm most proud of is the honesty: a 24-query benchmark with real
> IR metrics (P@K, R@K, MRR, nDCG) comparing four strategies, and docs that
> state where the approach falls short. Building it, I caught myself
> hard-filtering every parsed constraint — pools collapsed to 1–11 rows and
> the benchmark measured nothing. Fixing that became a documented design
> decision (soft constraints vs hard filters) and a good story about
> measuring instead of assuming.
>
> Runs with zero API keys — deterministic demo embeddings by default.
> Python/FastAPI · PostgreSQL+pgvector · Next.js. MIT.
>
> Repo: github.com/Nihal-MN/talentgraph-ai

## Demo script (5 minutes)

1. **Search** (30s) — type
   `senior python backend engineer in Berlin with kubernetes experience`.
   Point out: parsed chips (`skill: python`, `city: Berlin`, `seniority: senior`),
   latency, and that NL constraints are *soft signals* — the filter panel is
   where hard constraints live.
2. **Why this result?** (60s) — open the panel on #1: score breakdown
   (lexical rank 2, cosine 0.something, RRF, rerank), reranker notes with
   the geography boost `×1.40`, matched skills *with the quoted resume
   lines*, and the signals checklist. "Nothing here is decoration — every
   number is computed from this query."
3. **The synonym demo** (60s) — search `postgres`, strategy **Vector only**;
   then switch to **Lexical only**. Vector finds "PostgreSQL" docs that
   lexical misses. Then **Hybrid** to show the fusion combining both.
4. **Geography scoping** (30s) — `technical recruiter in the Gulf` → MENA
   recruiters rise with the region note; explain hard filters as the
   deterministic alternative.
5. **Rediscovery** (60s) — paste the sample JD → parsed requirements, top
   matches with explanations, and the explicit **gaps** list ("nothing in
   the pool matches Kafka — that's a sourcing brief").
6. **Evaluation** (60s) — the strategy table: lexical strong on exact terms,
   vector catching aliases, hybrid best MRR, reranker best nDCG. "This is
   the part most demos skip: we measured."
7. **Ingest** (30s) — paste a resume on the search page → it's parsed,
   embedded, searchable — same pipeline as the seed pool.

## Interview questions this project answers

**"How do you combine keyword and semantic search?"** — RRF with k=60;
rank-based so no score calibration; hybrid leads MRR in the benchmark.

**"How do you know your search is actually good?"** — 24-query golden set,
graded labels from generator ground truth, four strategies, P@K/R@K/MRR/
nDCG, persisted runs. And I document what the numbers *don't* prove
(synthetic labels measure mechanics, not human judgment).

**"What was your hardest design decision?"** — Soft vs hard constraints.
First version hard-filtered every parsed constraint; candidate pools
collapsed below the ranking window and every strategy tied. Rebuilt it so
only explicit filters hard-filter, prose constraints rank — benchmark
became meaningful (ADR 0003).

**"How do you handle synonyms/abbreviations?"** — Taxonomy canonicalization
("k8s" → kubernetes, "postgres" → postgresql) feeding both the parser and
the embedder; vector retrieval catches what literal search misses.

**"What about prompt injection / untrusted resumes?"** — Resumes are data:
parsed, quoted as evidence, never executed. The eval suite ships a hostile
resume fixture and asserts it gets no special treatment.

**"How do you avoid bias in ranking?"** — Protected characteristics can't
become filters or signals (the parser has no such outputs; eval 16 asserts
it). No automated decisions — ranking + evidence for a human. Demographic
data isn't collected in the dataset at all.

**"Why no neural embeddings by default?"** — The demo must run keyless and
deterministically; the demo embedder is explicitly lexical-semantic (its
limits are documented), and the OpenAI path is the production adapter.

**"How is this different from filtering a spreadsheet?"** — Evidence with
source quotes, measured ranking, synonym handling, JD rediscovery with
gaps, and analytics — with filters kept as the deterministic escape hatch.

## Numbers cheat-sheet

- Dataset: 200 deterministic synthetic profiles · 16 archetypes · ~150
  canonical skills · 260+ companies
- Pipeline latency: hybrid + rerank ≈ 50–70 ms on the demo pool (eval 18)
- Tests: 110 backend · 20 named evals · 12 frontend · CI on SQLite **and**
  pgvector · Docker builds green
- Benchmark (24 queries, k=10): see `docs/EVALUATION.md` — hybrid leads MRR,
  hybrid+rerank leads nDCG/P@10/R@10
