# ADR 0002 — Reciprocal Rank Fusion as the hybrid combiner

**Status:** accepted

**Context.** Hybrid search needs to combine a lexical ranking and a vector
ranking whose scores live on incomparable scales (ts_rank/BM25 vs cosine
similarity). Options: score normalization + weighted sum, learned fusion, or
rank-based fusion.

**Decision.** Use **Reciprocal Rank Fusion**: `score(d) = Σ_r 1/(k + rank_r(d))`,
`k = 60`. It is hyperparameter-light (one well-studied constant, no weights to
tune), scale-free by construction, and robust to one weak retriever — its
worst-case contribution is bounded by rank position, not by a miscalibrated
score. Per-strategy raw scores are still surfaced in the UI for transparency.

**Consequences.** Fusion gains are driven by *agreement* between retrievers,
not by absolute score margins — which matches how the benchmark reads
(hybrid wins on MRR across strategies; see `docs/EVALUATION.md`). If weighted
fusion is ever needed, weights are already a parameter.
