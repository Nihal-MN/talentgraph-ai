# Roadmap

Direction, not promises. Issue numbers appear when work starts.

## Next (v0.2)

- **Auth + multi-user**: accounts, per-user saved searches, audit of who ran
  what (the current demo is deliberately single-user/local).
- **Click-through analytics loops**: feed result clicks/saves back into the
  benchmark as calibration data and a learned reranker (the transparent
  feature reranker stays as the interpretable baseline).
- **CSV/JSONL bulk import** for candidate pools, alongside the paste-ingest.
- **Relevance feedback UI**: thumbs on results → persisted judgments →
  "golden set grows with you".

## Later

- **LLM reranker adapter** (listwise, explainable) behind the same interface
  as the feature reranker, measured against it in the benchmark.
- **Multilingual taxonomy packs** (starting with Arabic/Deutsch) including
  transliterated names and localized titles.
- **Scheduled rediscovery digests**: a saved search emails you when new
  candidates enter the pool above a score threshold.
- **Workflow hooks**: share a result list to ATS/CRM exports.
- **Scale**: IVFFlat/HNSW parameter tuning notes + bulk re-embedding jobs for
  pools in the 10⁵–10⁶ range.

## Explicitly not planned

- Scraping LinkedIn or any ToS-violating data source.
- Automated candidate rejection — this stays a human-decision tool.
- Protected-characteristic filtering or "diversity scoring" of any kind.
