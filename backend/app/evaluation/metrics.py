"""Information-retrieval metrics — textbook definitions, tested on toy cases.

All metrics take *graded* relevance (0 = irrelevant, 1 = acceptable, 2 = ideal).
Binary recall treats grade>0 as relevant. These are the exact functions the
benchmark page reports; nothing is estimated or hand-tuned.
"""

from __future__ import annotations

import math


def precision_at_k(retrieved_grades: list[int], k: int) -> float:
    """Fraction of the top-k results that are relevant (grade > 0)."""
    if k <= 0:
        return 0.0
    top = retrieved_grades[:k]
    relevant = sum(1 for grade in top if grade > 0)
    return relevant / k


def recall_at_k(retrieved_grades: list[int], k: int, total_relevant: int) -> float:
    if total_relevant <= 0:
        return 0.0
    top = retrieved_grades[:k]
    return sum(1 for grade in top if grade > 0) / total_relevant


def reciprocal_rank(retrieved_grades: list[int]) -> float:
    for index, grade in enumerate(retrieved_grades, start=1):
        if grade > 0:
            return 1.0 / index
    return 0.0


def dcg_at_k(gains: list[int], k: int) -> float:
    total = 0.0
    for index, gain in enumerate(gains[:k], start=1):
        total += (2**gain - 1) / math.log2(index + 1)
    return total


def ndcg_at_k(retrieved_grades: list[int], ideal_grades: list[int], k: int) -> float:
    """nDCG@k with graded gains; ideal_grades = all relevance grades for the
    query, sorted descending internally."""
    ideal = dcg_at_k(sorted(ideal_grades, reverse=True), k)
    if ideal == 0:
        return 0.0
    return dcg_at_k(retrieved_grades, k) / ideal


def evaluate_ranking(
    retrieved_grades: list[int], ideal_grades: list[int], k: int
) -> dict[str, float]:
    total_relevant = sum(1 for grade in ideal_grades if grade > 0)
    return {
        "precision_at_k": round(precision_at_k(retrieved_grades, k), 4),
        "recall_at_k": round(recall_at_k(retrieved_grades, k, total_relevant), 4),
        "mrr": round(reciprocal_rank(retrieved_grades), 4),
        "ndcg_at_k": round(ndcg_at_k(retrieved_grades, ideal_grades, k), 4),
        "total_relevant": total_relevant,
    }
