"""Lexical retrieval.

- PostgreSQL: real full-text search (``to_tsvector`` / ``websearch_to_tsquery``
  / ``ts_rank_cd``) with ``ts_headline`` snippets.
- SQLite dev/test fallback: Okapi BM25 computed in Python over the denormalized
  ``search_text`` column (200–500 docs — trivial cost, same interface).

Both return the same ``LexicalHit`` shape, with matched query terms and a
snippet suitable for "Why this result" evidence.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.normalize import tokenize

K1 = 1.2
B = 0.75
SNIPPET_WINDOW = 28  # tokens of context around the first match

_STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "with",
    "in",
    "of",
    "for",
    "on",
    "at",
    "to",
    "is",
    "are",
    "as",
    "by",
    "from",
    "that",
    "this",
    "who",
    "years",
    "year",
    "experience",
    "candidate",
    "candidates",
    "engineer",
    "engineers",
    "developer",
    "developers",
    "someone",
    "looking",
    "find",
    "me",
    "please",
    "who's",
    "whos",
    "have",
    "has",
    "plus",
    "strong",
    "good",
}


@dataclass
class LexicalHit:
    candidate_id: int
    score: float
    matched_terms: list[str] = field(default_factory=list)
    snippet: str = ""


def query_terms(text_input: str, limit: int = 12) -> list[str]:
    """Meaningful query tokens for lexical matching (stopwords removed)."""
    tokens = [token for token in tokenize(text_input) if token not in _STOPWORDS and len(token) > 2]
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
        if len(seen) >= limit:
            break
    return seen


def _snippet_for(search_text: str, terms: list[str]) -> str:
    words = search_text.split()
    lowered = [word.lower().strip(".,;:()") for word in words]
    for term in terms:
        for index, word in enumerate(lowered):
            if term in word:
                start = max(0, index - 4)
                end = min(len(words), index + SNIPPET_WINDOW)
                window = " ".join(words[start:end])
                return f"…{window.strip()}…"
    return " ".join(words[:24])


class LexicalSearcher:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dialect = db.get_bind().dialect.name

    def search(
        self,
        query_text: str,
        candidate_ids: list[int] | None = None,
        limit: int = 50,
    ) -> list[LexicalHit]:
        terms = query_terms(query_text)
        if not terms:
            return []
        if self.dialect == "postgresql":
            return self._search_postgres(query_text, terms, candidate_ids, limit)
        return self._search_bm25(terms, candidate_ids, limit)

    # ── PostgreSQL FTS ────────────────────────────────────────────────────
    def _search_postgres(
        self,
        query_text: str,
        terms: list[str],
        candidate_ids: list[int] | None,
        limit: int,
    ) -> list[LexicalHit]:
        fts_query = " OR ".join(terms)
        id_clause = "AND c.id = ANY(:ids)" if candidate_ids is not None else ""
        sql = text(
            f"""
            SELECT c.id AS candidate_id,
                   ts_rank_cd(
                       to_tsvector('english', c.search_text),
                       websearch_to_tsquery('english', :q)
                   ) AS score,
                   ts_headline(
                       'english', left(c.search_text, 4000),
                       websearch_to_tsquery('english', :q),
                       'MaxFragments=1, MaxWords=26, MinWords=8, StartSel=[, StopSel=]'
                   ) AS snippet
            FROM candidates c
            WHERE to_tsvector('english', c.search_text)
                  @@ websearch_to_tsquery('english', :q)
            {id_clause}
            ORDER BY score DESC
            LIMIT :limit
            """  # noqa: S608 — static SQL, parameters bound
        )
        params: dict = {"q": fts_query, "limit": limit}
        if candidate_ids is not None:
            params["ids"] = candidate_ids
        rows = self.db.execute(sql, params).mappings().all()
        hits = [
            LexicalHit(
                candidate_id=row["candidate_id"],
                score=float(row["score"]),
                matched_terms=terms,
                snippet=row["snippet"] or "",
            )
            for row in rows
        ]
        return hits

    # ── SQLite BM25 fallback ──────────────────────────────────────────────
    def _search_bm25(
        self,
        terms: list[str],
        candidate_ids: list[int] | None,
        limit: int,
    ) -> list[LexicalHit]:
        if candidate_ids is not None:
            placeholders = ",".join(str(int(cid)) for cid in candidate_ids) or "0"
            rows = (
                self.db.execute(
                    text(f"SELECT id, search_text FROM candidates WHERE id IN ({placeholders})")
                )
                .mappings()
                .all()
            )
        else:
            rows = self.db.execute(text("SELECT id, search_text FROM candidates")).mappings().all()

        documents: list[tuple[int, list[str], str]] = []
        for row in rows:
            search_text = row["search_text"] or ""
            documents.append((row["id"], tokenize(search_text), search_text))

        count = len(documents)
        if count == 0:
            return []
        avg_len = sum(len(tokens) for _id, tokens, _text in documents) / count
        doc_freq: dict[str, int] = {term: 0 for term in terms}
        for _id, tokens, _text in documents:
            token_set = set(tokens)
            for term in terms:
                if term in token_set:
                    doc_freq[term] += 1

        hits: list[LexicalHit] = []
        for candidate_id, tokens, search_text in documents:
            length = len(tokens) or 1
            score = 0.0
            matched: list[str] = []
            counts: dict[str, int] = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for term in terms:
                frequency = counts.get(term, 0)
                if frequency == 0:
                    continue
                matched.append(term)
                idf = math.log(1 + (count - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
                score += (
                    idf * (frequency * (K1 + 1)) / (frequency + K1 * (1 - B + B * length / avg_len))
                )
            if score > 0:
                hits.append(
                    LexicalHit(
                        candidate_id=candidate_id,
                        score=round(score, 6),
                        matched_terms=matched,
                        snippet=_snippet_for(search_text, matched or terms),
                    )
                )
        hits.sort(key=lambda hit: (-hit.score, hit.candidate_id))
        return hits[:limit]


def highlight_terms(snippet: str, terms: list[str]) -> str:
    """Wrap matched terms in «» for display (idempotent-ish helper for the UI)."""
    if not snippet:
        return snippet
    pattern = re.compile(
        r"(?<![a-zA-Z0-9])(" + "|".join(re.escape(term) for term in terms) + r")(?![a-zA-Z0-9])",
        re.IGNORECASE,
    )
    return pattern.sub(lambda match: f"«{match.group(0)}»", snippet)
