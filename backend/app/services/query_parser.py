"""Natural-language query parsing (search intent → structured query).

Two interchangeable parsers behind one interface:

- ``RuleBasedParser`` — deterministic, keyless: taxonomy-driven skill/alias
  extraction, years & seniority patterns, city/country resolution, industry and
  title-family detection, plus a free-text remainder for lexical/vector scoring.
- ``LLMQueryParser`` — OpenAI structured output (stub-tested; active when a key
  is configured). Falls back to the rule-based parser on any provider failure,
  and *says so* in the parse notes — no silent degradation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.services.normalize import (
    detect_seniority,
    expand_skills,
    extract_skills,
    find_location,
    is_remote_mention,
    parse_years,
    tokenize,
)
from app.services.taxonomy import DOMAIN_KEYWORDS, TITLE_FAMILIES

FILLER_WORDS = {
    "find",
    "me",
    "show",
    "looking",
    "for",
    "a",
    "an",
    "the",
    "with",
    "who",
    "has",
    "have",
    "candidates",
    "candidate",
    "profiles",
    "profile",
    "people",
    "someone",
    "engineers",
    "engineer",
    "developers",
    "developer",
    "experience",
    "experienced",
    "years",
    "year",
    "yrs",
    "in",
    "based",
    "from",
    "at",
    "least",
    "minimum",
    "plus",
    "strong",
    "good",
    "great",
    "and",
    "or",
    "of",
    "to",
    "is",
    "are",
    "who's",
    "whos",
    "that",
    "this",
    "preferably",
    "ideally",
    "must",
    "should",
    "about",
    "around",
    "senior",
    "junior",
    "mid",
    "lead",
    "staff",
    "principal",
    "head",
}


@dataclass
class ParsedQuery:
    raw: str
    text_terms: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    expansions: list[str] = field(default_factory=list)
    min_years: float | None = None
    max_years: float | None = None
    seniority: list[str] = field(default_factory=list)
    city: str | None = None
    country: str | None = None
    region: str | None = None
    remote: bool = False
    industry: str | None = None
    family: str | None = None
    notes: list[str] = field(default_factory=list)
    parser: str = "rule-based"

    def to_filters(self) -> dict:
        filters: dict = {}
        if self.skills:
            filters["skills"] = self.skills
        if self.min_years is not None:
            filters["min_years"] = self.min_years
        if self.max_years is not None:
            filters["max_years"] = self.max_years
        if self.seniority:
            filters["seniority"] = self.seniority
        if self.city:
            filters["cities"] = [self.city]
        elif self.country:
            filters["countries"] = [self.country]
        if self.region:
            filters["region"] = self.region
        if self.industry:
            filters["industry"] = self.industry
        if self.family:
            filters["family"] = self.family
        return filters


class QueryParser(Protocol):
    name: str

    def parse(self, raw: str) -> ParsedQuery: ...


def _remove_phrase(text: str, phrase: str) -> str:
    pattern = re.compile(re.escape(phrase).replace(r"\ ", r"\s+"), re.IGNORECASE)
    return pattern.sub(" ", text)


class RuleBasedParser:
    name = "rule-based"

    def parse(self, raw: str) -> ParsedQuery:
        parsed = ParsedQuery(raw=raw, parser=self.name)
        working = raw

        # skills (longest aliases first; each match removed from the remainder)
        for match in extract_skills(raw, max_skills=8):
            parsed.skills.append(match["canonical"])
            working = _remove_phrase(working, match["matched_alias"])
        if parsed.skills:
            parsed.expansions = [
                skill for skill in expand_skills(parsed.skills) if skill not in parsed.skills
            ]

        # years
        parsed.min_years = parse_years(raw)
        pair = re.search(r"(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\s*(?:years|yrs)", raw, re.I)
        if pair:
            parsed.min_years = float(pair.group(1))
            parsed.max_years = float(pair.group(2))
            working = _remove_phrase(working, pair.group(0))
        elif parsed.min_years is not None:
            working = re.sub(
                r"(?:at least|minimum(?: of)?|min\.?)?\s*\d{1,2}\s*\+?\s*(?:years|yrs)(?:\s+of)?"
                r"(?:\s+experience)?",
                " ",
                working,
                flags=re.I,
            )

        # seniority
        seniority = detect_seniority(raw)
        if seniority:
            parsed.seniority = [seniority]
            for word in ("senior", "junior", "lead", "staff", "principal"):
                working = re.sub(rf"\b{word}\b", " ", working, flags=re.I)

        # location
        location = find_location(raw)
        if location:
            parsed.city = location.get("city")
            parsed.country = location.get("country")
            parsed.region = location.get("region")
            for alias in (parsed.city, parsed.country):
                if alias:
                    working = _remove_phrase(working, alias)
        parsed.remote = is_remote_mention(raw)
        if parsed.remote:
            parsed.notes.append(
                "remote mentioned — the synthetic dataset stores office locations only"
            )

        # industry / domain
        lowered = raw.lower()
        for industry, keywords in DOMAIN_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                parsed.industry = industry
                break

        # title family
        for family, keywords in TITLE_FAMILIES.items():
            if any(keyword in lowered for keyword in keywords):
                parsed.family = family
                break

        # free-text remainder
        terms: list[str] = []
        for token in tokenize(working):
            if token in FILLER_WORDS or len(token) < 3:
                continue
            if token in terms:
                continue
            terms.append(token)
        parsed.text_terms = terms[:12]

        if not parsed.skills and parsed.text_terms:
            # recanonicalize: a free-term may itself be a skill alias that we
            # failed to match as a phrase (rare); try single tokens
            for term in list(parsed.text_terms):
                from app.services.normalize import canonical_for

                canonical = canonical_for(term)
                if canonical and canonical not in parsed.skills:
                    parsed.skills.append(canonical)
                    parsed.expansions = [
                        skill
                        for skill in expand_skills(parsed.skills)
                        if skill not in parsed.skills
                    ]
                    parsed.text_terms.remove(term)
        return parsed


class LLMQueryParser:
    """OpenAI structured-output parser with an honest rule-based fallback."""

    name = "llm"

    def __init__(self, client, model: str) -> None:
        self._client = client
        self._model = model
        self._fallback = RuleBasedParser()

    def parse(self, raw: str) -> ParsedQuery:
        try:
            return self._parse_with_llm(raw)
        except Exception as exc:  # noqa: BLE001 — provider failures fall back, visibly
            parsed = self._fallback.parse(raw)
            parsed.notes.append(
                f"LLM parse failed ({type(exc).__name__}); rule-based fallback used"
            )
            return parsed

    def _parse_with_llm(self, raw: str) -> ParsedQuery:
        response = self._client.responses.create(
            model=self._model,
            instructions=(
                "Extract structured recruiting search intent as JSON. Fields: "
                "skills (array of lowercase canonical skill names), min_years "
                "(number|null), max_years (number|null), seniority (array among "
                "junior/mid/senior/lead/staff/principal/head), city (string|null), "
                "country (string|null), text_terms (array of remaining keywords). "
                "Never include protected characteristics. Output JSON only."
            ),
            input=raw,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "parsed_query",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "skills": {"type": "array", "items": {"type": "string"}},
                            "min_years": {"type": ["number", "null"]},
                            "max_years": {"type": ["number", "null"]},
                            "seniority": {"type": "array", "items": {"type": "string"}},
                            "city": {"type": ["string", "null"]},
                            "country": {"type": ["string", "null"]},
                            "text_terms": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": [
                            "skills",
                            "min_years",
                            "max_years",
                            "seniority",
                            "city",
                            "country",
                            "text_terms",
                        ],
                    },
                }
            },
        )
        import json

        payload = json.loads(response.output_text)
        parsed = ParsedQuery(raw=raw, parser=self.name)
        parsed.skills = [str(skill).lower() for skill in payload.get("skills", [])][:8]
        parsed.expansions = [
            skill for skill in expand_skills(parsed.skills) if skill not in parsed.skills
        ]
        parsed.min_years = payload.get("min_years")
        parsed.max_years = payload.get("max_years")
        parsed.seniority = payload.get("seniority") or []
        parsed.city = payload.get("city")
        parsed.country = payload.get("country")
        parsed.text_terms = [str(term) for term in payload.get("text_terms", [])][:12]
        if parsed.city or parsed.country:
            location = find_location(f"{parsed.city or ''} {parsed.country or ''}")
            if location:
                parsed.region = location.get("region")
        return parsed


@lru_cache
def get_query_parser() -> QueryParser:
    settings = get_settings()
    if settings.resolved_ai_mode == "openai" and settings.openai_api_key:
        from openai import OpenAI

        return LLMQueryParser(OpenAI(api_key=settings.openai_api_key), settings.openai_chat_model)
    return RuleBasedParser()
