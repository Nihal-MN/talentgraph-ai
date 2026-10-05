"""RRF fusion + normalization tests."""

from __future__ import annotations

from app.services.fusion import normalize_scores, reciprocal_rank_fusion


class TestRRF:
    def test_formula_matches_definition(self):
        rankings = {"lexical": [1, 2], "vector": [2, 1]}
        fused = reciprocal_rank_fusion(rankings, k=60)
        by_id = {hit.candidate_id: hit for hit in fused}
        # candidate 1: rank 1 in lexical, rank 2 in vector
        expected = 1 / 61 + 1 / 62
        assert abs(by_id[1].score - expected) < 1e-8  # stored rounded to 8 dp
        assert by_id[1].ranks == {"lexical": 1, "vector": 2}

    def test_document_in_only_one_list_still_scores(self):
        fused = reciprocal_rank_fusion({"lexical": [9], "vector": []}, k=60)
        assert fused[0].candidate_id == 9
        assert abs(fused[0].score - 1 / 61) < 1e-8  # stored rounded to 8 dp

    def test_agreement_beats_single_list_strength(self):
        # A is top-1 in both lists; B is top-1 in one list only
        fused = reciprocal_rank_fusion(
            {"lexical": [1, 2], "vector": [1, 2]},
            k=60,
        )
        assert [hit.candidate_id for hit in fused] == [1, 2]

    def test_empty_rankings(self):
        assert reciprocal_rank_fusion({}, k=60) == []


class TestNormalizeScores:
    def test_scales_to_unit_interval(self):
        fused = reciprocal_rank_fusion({"a": [1, 2, 3]}, k=60)
        normalized = normalize_scores(fused)
        assert max(normalized.values()) == 1.0
        assert min(normalized.values()) == 0.0  # min-max scaling

    def test_single_hit_is_one(self):
        fused = reciprocal_rank_fusion({"a": [7]}, k=60)
        assert normalize_scores(fused) == {7: 1.0}

    def test_all_equal_is_one(self):
        fused = reciprocal_rank_fusion({"a": [1], "b": [2]}, k=60, weights={"a": 0.5, "b": 0.5})
        normalized = normalize_scores(fused)
        assert set(normalized.values()) == {1.0}

    def test_empty(self):
        assert normalize_scores([]) == {}
