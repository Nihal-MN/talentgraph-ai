"""Vector retrieval.

- PostgreSQL + pgvector: ``ORDER BY embedding <=> CAST(:query AS vector)`` —
  native ANN-ready query (HNSW index created when the extension is present).
- SQLite fallback: cosine similarity computed in Python over stored JSON
  vectors (fine for the 100–500 doc demo scale, identical results).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embedding import cosine_similarity


@dataclass
class VectorHit:
    candidate_id: int
    similarity: float


def _to_pg_vector(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.7f}" for value in vector) + "]"


class VectorSearcher:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.dialect = db.get_bind().dialect.name

    def search(
        self,
        query_vector: list[float],
        candidate_ids: list[int] | None = None,
        limit: int = 50,
    ) -> list[VectorHit]:
        if self.dialect == "postgresql":
            return self._search_pgvector(query_vector, candidate_ids, limit)
        return self._search_python(query_vector, candidate_ids, limit)

    def _search_pgvector(
        self,
        query_vector: list[float],
        candidate_ids: list[int] | None,
        limit: int,
    ) -> list[VectorHit]:
        id_clause = "AND e.candidate_id = ANY(:ids)" if candidate_ids is not None else ""
        sql = text(
            f"""
            SELECT e.candidate_id,
                   1 - (e.embedding <=> CAST(:vec AS vector)) AS similarity
            FROM candidate_embeddings e
            WHERE e.embedding IS NOT NULL
            {id_clause}
            ORDER BY e.embedding <=> CAST(:vec AS vector)
            LIMIT :limit
            """  # noqa: S608 — static SQL, parameters bound
        )
        params: dict = {"vec": _to_pg_vector(query_vector), "limit": limit}
        if candidate_ids is not None:
            params["ids"] = candidate_ids
        rows = self.db.execute(sql, params).mappings().all()
        return [
            VectorHit(candidate_id=row["candidate_id"], similarity=float(row["similarity"]))
            for row in rows
        ]

    def _search_python(
        self,
        query_vector: list[float],
        candidate_ids: list[int] | None,
        limit: int,
    ) -> list[VectorHit]:
        if candidate_ids is not None:
            placeholders = ",".join(str(int(cid)) for cid in candidate_ids) or "0"
            rows = (
                self.db.execute(
                    text(
                        "SELECT candidate_id, embedding FROM candidate_embeddings "
                        f"WHERE candidate_id IN ({placeholders})"
                    )
                )
                .mappings()
                .all()
            )
        else:
            rows = (
                self.db.execute(text("SELECT candidate_id, embedding FROM candidate_embeddings"))
                .mappings()
                .all()
            )

        import json

        hits: list[VectorHit] = []
        for row in rows:
            raw = row["embedding"]
            if raw is None:
                continue
            try:
                vector = raw if isinstance(raw, list) else json.loads(str(raw))
            except Exception:  # noqa: BLE001 — malformed row, skip
                continue
            hits.append(
                VectorHit(
                    candidate_id=row["candidate_id"],
                    similarity=cosine_similarity(query_vector, [float(v) for v in vector]),
                )
            )
        hits.sort(key=lambda hit: (-hit.similarity, hit.candidate_id))
        return hits[:limit]
