"""IR metric tests — textbook definitions on hand-computed toy cases."""

from __future__ import annotations

import math

from app.evaluation.metrics import (
    dcg_at_k,
    evaluate_ranking,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


class TestPrecisionRecall:
    def test_precision_prefix(self):
        grades = [2, 0, 1, 0, 2]
        assert precision_at_k(grades, 1) == 1.0
        assert precision_at_k(grades, 2) == 0.5
        assert precision_at_k(grades, 5) == 0.6

    def test_precision_divides_by_k_not_result_count(self):
        # two perfect results, k=4 → 2/4, the standard definition
        assert precision_at_k([2, 2], 4) == 0.5

    def test_recall(self):
        assert recall_at_k([2, 0, 1, 0], 4, total_relevant=2) == 1.0
        assert recall_at_k([0, 2, 0, 0], 4, total_relevant=4) == 0.25
        assert recall_at_k([2], 1, total_relevant=0) == 0.0


class TestMRR:
    def test_first_relevant_position(self):
        assert reciprocal_rank([0, 0, 2]) == 1 / 3
        assert reciprocal_rank([1, 0, 0]) == 1.0
        assert reciprocal_rank([0, 0, 0]) == 0.0


class TestNDCG:
    def test_known_small_example(self):
        # retrieved [2, 0, 1]; ideal [2, 1, 0]
        retrieved = [2, 0, 1]
        ideal = [2, 1, 0]
        expected = (3 + 0 + 0.5) / (3 + 1 / math.log2(3))
        assert abs(ndcg_at_k(retrieved, ideal, 3) - expected) < 1e-9

    def test_perfect_is_one(self):
        assert ndcg_at_k([2, 1, 0], [2, 1, 0], 3) == 1.0

    def test_zero_ideal_is_zero(self):
        assert ndcg_at_k([0, 0], [0, 0], 2) == 0.0

    def test_dcg_gain_shape(self):
        assert dcg_at_k([2], 1) == 3.0  # (2^2 - 1) / log2(2)
        assert dcg_at_k([1], 1) == 1.0


class TestEvaluateRanking:
    def test_bundles_all_metrics(self):
        result = evaluate_ranking([2, 0, 1], [2, 1, 0, 1], 3)
        assert set(result) == {
            "precision_at_k",
            "recall_at_k",
            "mrr",
            "ndcg_at_k",
            "total_relevant",
        }
        assert result["total_relevant"] == 3
        assert result["mrr"] == 1.0
