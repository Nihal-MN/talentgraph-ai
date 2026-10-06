"""Normalization unit tests — skills, titles, years, locations."""

from __future__ import annotations

from app.services.normalize import (
    detect_seniority,
    extract_skills,
    find_location,
    normalize_title,
    parse_years,
)


class TestExtractSkills:
    def test_canonical_and_alias(self):
        found = {match["canonical"] for match in extract_skills("Strong in Python and K8s.")}
        assert "python" in found
        assert "kubernetes" in found  # via alias "k8s"

    def test_multiword_alias_beats_substring(self):
        found = {match["canonical"] for match in extract_skills("Built apps with React Native.")}
        assert "react-native" in found
        assert "react" not in found  # masked by the longer match

    def test_plain_react_still_matches(self):
        found = {match["canonical"] for match in extract_skills("Built apps with React.js")}
        assert "react" in found

    def test_evidence_is_the_containing_line(self):
        text = "Intro line\nDesigned PostgreSQL workloads at scale\nFooter"
        match = next(match for match in extract_skills(text) if match["canonical"] == "postgresql")
        assert "PostgreSQL workloads" in match["evidence"]
        assert "Intro line" not in match["evidence"]

    def test_no_nul_bytes_in_evidence_or_alias(self):
        # Regression: evidence used to be sliced from the masked working copy,
        # leaking \x00 filler for previously matched spans in the same line —
        # PostgreSQL rejects NUL bytes in text columns.
        text = (
            "Senior Engineer\n"
            "Built embeddings pipelines and vector database infrastructure "
            "on AWS with PyTorch and RAG.\n"
        )
        matches = extract_skills(text)
        assert len(matches) >= 4
        for match in matches:
            assert "\x00" not in match["evidence"]
            assert "\x00" not in match["matched_alias"]
        aws = next(match for match in matches if match["canonical"] == "aws")
        assert "Built embeddings pipelines and vector database infrastructure" in aws["evidence"]

    def test_no_duplicates_and_cap(self):
        text = "python " * 30
        matches = extract_skills(text, max_skills=5)
        canonicals = [match["canonical"] for match in matches]
        assert len(canonicals) == len(set(canonicals))
        assert len(canonicals) <= 5

    def test_returns_empty_for_plain_prose(self):
        assert extract_skills("We went for a long walk yesterday.") == []


class TestNormalizeTitle:
    def test_senior_backend(self):
        result = normalize_title("Senior Backend Software Engineer")
        assert result["seniority"] == "senior"
        assert result["family"] == "backend engineer"

    def test_junior_frontend(self):
        result = normalize_title("Junior Frontend Developer")
        assert result["seniority"] == "junior"
        assert result["family"] == "frontend engineer"

    def test_recruiter_family(self):
        assert normalize_title("Technical Recruiter")["family"] == "recruiter"

    def test_unknown_title(self):
        result = normalize_title("Chief Vibes Officer")
        assert result["family"] is None


class TestParseYears:
    def test_plus_pattern(self):
        assert parse_years("5+ years of experience") == 5.0

    def test_at_least_pattern(self):
        assert parse_years("at least 3 years building APIs") == 3.0

    def test_range_returns_first(self):
        assert parse_years("3-6 years experience") == 3.0

    def test_none_when_absent(self):
        assert parse_years("experienced engineer wanted") is None


class TestFindLocation:
    def test_earliest_mention_wins(self):
        result = find_location("Based in Dubai, United Arab Emirates. MSc from NUS Singapore.")
        assert result == {"city": "Dubai", "country": "United Arab Emirates", "region": "MENA"}

    def test_country_only(self):
        result = find_location("Candidates based in Germany preferred")
        assert result is not None
        assert result["country"] == "Germany"
        assert result["city"] is None

    def test_region_alias(self):
        result = find_location("recruiters in the Gulf")
        assert result == {"city": None, "country": None, "region": "MENA"}

    def test_no_location(self):
        assert find_location("remote-friendly team") is None

    def test_detect_seniority(self):
        assert detect_seniority("we need a staff engineer") == "staff"
        assert detect_seniority("plain description") is None
