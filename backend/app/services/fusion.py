"""Hybrid fusion via Reciprocal Rank Fusion (RRF).

RRF is the standard, hyperparameter-light way to combine heterogeneous
rankings: ``score(d) = Σ_r weight_r / (k + rank_r(d))``. It needs no score
calibration between lexical and vector spaces — the reason it is the default
fusion here (see docs/adr/0002).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FusedHit:
    candidate_id: int
    score: float
    ranks: dict[str, int] = field(default_factory=dict)  # strategy -> rank (1-based)
    raw_scores: dict[str, float] = field(default_factory=dict)


def reciprocal_rank_fusion(
    rankings: dict[str, list[int]],
    *,
    k: int = 60,
    weights: dict[str, float] | None = None,
    raw_scores: dict[str, dict[int, float]] | None = None,
) -> list[FusedHit]:
    """rankings: {strategy: [candidate_id, ...] ordered best-first}."""
    weights = weights or {strategy: 1.0 for strategy in rankings}
    raw_scores = raw_scores or {}
    scores: dict[int, float] = {}
    ranks: dict[int, dict[str, int]] = {}

    for strategy, ordered_ids in rankings.items():
        weight = weights.get(strategy, 1.0)
        for position, candidate_id in enumerate(ordered_ids, start=1):
            scores[candidate_id] = scores.get(candidate_id, 0.0) + weight / (k + position)
            ranks.setdefault(candidate_id, {})[strategy] = position

    fused = [
        FusedHit(
            candidate_id=candidate_id,
            score=round(score, 8),
            ranks=ranks[candidate_id],
            raw_scores={
                strategy: raw_scores.get(strategy, {}).get(candidate_id, 0.0)
                for strategy in ranks[candidate_id]
            },
        )
        for candidate_id, score in scores.items()
    ]
    fused.sort(key=lambda hit: (-hit.score, hit.candidate_id))
    return fused


def normalize_scores(fused: list[FusedHit]) -> dict[int, float]:
    """Min-max normalize fused scores to [0, 1] for display/reranker input."""
    if not fused:
        return {}
    values = [hit.score for hit in fused]
    low, high = min(values), max(values)
    span = high - low or 1.0
    return {hit.candidate_id: (hit.score - low) / span for hit in fused}
