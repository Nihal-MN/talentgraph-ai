# ADR 0003 — Soft constraints vs hard filters

**Status:** accepted

**Context.** A natural-language query like "senior Python engineer in Berlin
with 5+ years" parses into skills, seniority, city and years. The obvious
implementation turns each into a SQL filter — and it degrades search
disastrously: early testing collapsed candidate pools to 1–11 rows per query,
below any ranking window, so lexical/vector/hybrid all returned identical
results and the benchmark measured nothing. It also mismatches recruiter
intent: "Berlin" usually means "Berlin preferred", not "Berlin mandatory".

**Decision.** Constraints parsed from prose are **soft ranking signals**
(reranker inputs + evidence annotations). Constraints provided *explicitly*
via the filter panel or API are **hard SQL constraints**. The split is
visible end-to-end: responses report `soft_signals` and `filters_used`
separately, the UI labels the filter panel "hard constraints", and each
result's "Why" panel shows which soft signals it satisfies.

**Consequences.** NL search always has a ranking window to work with; filters
do exactly what they say; users who truly want hard constraints state them
explicitly (one click in the panel). The benchmark compares strategies on
full-pool retrieval — where strategy differences actually exist.
