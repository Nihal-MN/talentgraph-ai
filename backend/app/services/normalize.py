"""Text normalization: skill extraction, title normalization, years parsing.

Everything here is deterministic and dependency-free — the same functions run
in the seed generator, the ingestion pipeline, the query parser and the demo
embedder, so the whole system agrees on what "k8s" means.
"""

from __future__ import annotations

import re

from app.services.taxonomy import (
    COUNTRY_ALIASES,
    LOCATIONS,
    SENIORITY_WORDS,
    SKILLS,
    TITLE_FAMILIES,
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./\-]*")

# Pre-built alias index: alias -> canonical, longest aliases first, with a
# compiled word-boundary pattern that tolerates flexible whitespace.
_ALIAS_INDEX: list[tuple[str, str, re.Pattern[str]]] = []
for _canonical, _meta in SKILLS.items():
    _forms = {_canonical, *_meta.get("aliases", [])}
    for _form in _forms:
        escaped = re.escape(_form).replace(r"\ ", r"\s+")
        _ALIAS_INDEX.append(
            (_form, _canonical, re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.IGNORECASE))
        )
_ALIAS_INDEX.sort(key=lambda item: len(item[0]), reverse=True)


def tokenize(text: str) -> list[str]:
    """Lowercase token stream; keeps c++, c#, .net, ci/cd style tokens."""
    return [token.rstrip(".") for token in _TOKEN_RE.findall(text.lower()) if token.rstrip(".")]


def canonical_for(token_or_alias: str) -> str | None:
    """Exact alias lookup for a single token (used by the demo embedder)."""
    lowered = token_or_alias.lower()
    for form, canonical, _pattern in _ALIAS_INDEX:
        if form == lowered:
            return canonical
    return None


def expand_skills(canonical_names: list[str]) -> list[str]:
    """Canonical + related skills (the expansion graph used for retrieval)."""
    expanded: list[str] = []
    seen: set[str] = set()
    for name in canonical_names:
        if name in seen:
            continue
        seen.add(name)
        expanded.append(name)
        for related in SKILLS.get(name, {}).get("related", []):
            related_lower = related.lower()
            if related_lower not in seen:
                seen.add(related_lower)
                expanded.append(related_lower)
    return expanded


def extract_skills(text: str, max_skills: int = 40) -> list[dict]:
    """Find canonical skills in free text.

    Returns [{"canonical", "matched_alias", "evidence"}] with the containing
    line as evidence. Longest aliases win; matched spans are masked so
    "react native" doesn't also report "react".
    """
    found: list[dict] = []
    seen: set[str] = set()
    masked = text
    for _form, canonical, pattern in _ALIAS_INDEX:
        if canonical in seen:
            continue
        match = pattern.search(masked)
        if not match:
            continue
        # Evidence and the alias always come from the ORIGINAL text — the
        # working copy's masked spans contain NUL filler, and PostgreSQL
        # rejects NUL bytes in text columns outright (SQLite silently allowed
        # them; the pgvector CI job caught it).
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        evidence = text[line_start : line_end if line_end != -1 else None].strip()
        alias = text[match.start() : match.end()]
        found.append(
            {
                "canonical": canonical,
                "matched_alias": alias.replace("\x00", ""),
                "evidence": evidence.replace("\x00", "")[:300],
            }
        )
        seen.add(canonical)
        masked = (
            masked[: match.start()]
            + ("\x00" * (match.end() - match.start()))
            + masked[match.end() :]
        )
        if len(found) >= max_skills:
            break
    return found


def normalize_title(title: str) -> dict:
    """→ {"normalized_title", "seniority", "family"} best-effort extraction."""
    lowered = f" {title.lower()} "
    seniority = None
    for level in ("head", "principal", "staff", "lead", "senior", "junior", "intern", "mid"):
        if any(word in lowered for word in SENIORITY_WORDS[level]):
            seniority = level
            break
    family = None
    for candidate_family, keywords in TITLE_FAMILIES.items():
        if any(keyword in lowered for keyword in keywords):
            family = candidate_family
            break
    if family is None:
        # fall back to the most specific skill category present in the title
        skills = extract_skills(title, max_skills=3)
        if skills:
            family = f"{skills[0]['canonical']} specialist"
    normalized = title.strip()
    if seniority and family and seniority not in lowered.split():
        normalized = f"{seniority} {family}"
    return {"normalized_title": normalized, "seniority": seniority, "family": family}


_YEARS_PATTERNS = [
    re.compile(r"(?:at least|minimum(?: of)?|min\.?)\s+(\d{1,2})(?:\+)?\s*(?:years|yrs)", re.I),
    re.compile(r"(\d{1,2})\s*\+\s*(?:years|yrs)", re.I),
    re.compile(r"(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\s*(?:years|yrs)", re.I),
    re.compile(r"(\d{1,2})\s*(?:years|yrs)(?:\s+of)?(?:\s+experience)?", re.I),
]


def parse_years(text: str) -> float | None:
    """Extract the minimum years-of-experience mentioned in a query/JD."""
    for pattern in _YEARS_PATTERNS:
        match = pattern.search(text)
        if match:
            return float(match.group(1))
    return None


def detect_seniority(text: str) -> str | None:
    lowered = f" {text.lower()} "
    for level in ("head", "principal", "staff", "lead", "senior", "junior", "intern", "mid"):
        if any(word in lowered for word in SENIORITY_WORDS[level]):
            return level
    return None


REGION_ALIASES = {
    "gulf": "MENA",
    "gcc": "MENA",
    "middle east": "MENA",
    "european union": "Europe",
    "dach": "Europe",
    "nordics": "Europe",
    "apac": "APAC",
    "southeast asia": "APAC",
}


def find_location(text: str) -> dict | None:
    """Find the *earliest* city, country or region-group mention.

    Earliest-position wins so "Based in Dubai ... NUS Singapore" resolves to
    Dubai (the stated home) rather than a later incidental mention.
    """
    lowered = text.lower()
    best: tuple[int, dict] | None = None

    def consider(position: int, payload: dict) -> None:
        nonlocal best
        if best is None or position < best[0]:
            best = (position, payload)

    for alias in sorted(LOCATIONS, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(alias)}\b", lowered)
        if match:
            city, country, region = LOCATIONS[alias]
            consider(match.start(), {"city": city, "country": country, "region": region})
    for alias in sorted(COUNTRY_ALIASES, key=len, reverse=True):
        match = re.search(rf"\b{re.escape(alias)}\b", lowered)
        if match:
            consider(
                match.start(),
                {"city": None, "country": COUNTRY_ALIASES[alias], "region": None},
            )
    if best is not None:
        return best[1]
    for alias, region in REGION_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return {"city": None, "country": None, "region": region}
    return None


def is_remote_mention(text: str) -> bool:
    return bool(re.search(r"\b(remote|work from home|wfh|anywhere)\b", text, re.I))
