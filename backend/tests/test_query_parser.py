"""Query parser unit tests (rule-based, keyless)."""

from __future__ import annotations

from app.services.query_parser import RuleBasedParser


class TestRuleBasedParser:
    def setup_method(self):
        self.parser = RuleBasedParser()

    def test_skills_seniority_location(self):
        parsed = self.parser.parse("senior python backend engineer in Berlin with kubernetes")
        assert "python" in parsed.skills
        assert "kubernetes" in parsed.skills
        assert parsed.seniority == ["senior"]
        assert parsed.city == "Berlin"
        assert parsed.family == "backend engineer"
        assert "backend" in parsed.text_terms  # residual keyword kept for retrieval

    def test_years(self):
        parsed = self.parser.parse("data engineer with 5+ years of experience")
        assert parsed.min_years == 5.0

    def test_region_alias(self):
        parsed = self.parser.parse("technical recruiter in the Gulf")
        assert parsed.region == "MENA"
        assert parsed.family == "recruiter"

    def test_expansions_include_related(self):
        parsed = self.parser.parse("kubernetes engineer")
        assert "docker" in parsed.expansions or "helm" in parsed.expansions
        assert "kubernetes" not in parsed.expansions  # expansions exclude the skills themselves

    def test_no_protected_characteristics(self):
        parsed = self.parser.parse("young female sales manager")
        payload = parsed.to_filters()
        for forbidden in ("gender", "age", "sex", "nationality", "religion"):
            assert forbidden not in payload
        # "young"/"female" must not turn into any filter
        assert payload.get("seniority") in (None, [])
        assert "female" not in parsed.skills
