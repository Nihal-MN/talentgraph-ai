"""Search endpoints — the core of the product."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.schemas import SearchIn
from app.models import SearchQuery, SearchResult
from app.services.search_service import SearchRequest, run_search

router = APIRouter()


@router.post("/search")
def search(payload: SearchIn, db: DbSession) -> dict:
    outcome = run_search(
        db,
        SearchRequest(
            raw_query=payload.query,
            filters=payload.filters.model_dump(exclude_none=True) if payload.filters else {},
            strategy=payload.strategy,
            limit=payload.limit,
            rerank=payload.rerank,
        ),
    )
    return outcome


@router.get("/search/recent")
def recent_searches(db: DbSession, limit: int = Query(default=20, ge=1, le=100)) -> list[dict]:
    rows = db.scalars(
        select(SearchQuery).order_by(SearchQuery.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": row.id,
            "raw_query": row.raw_query,
            "strategy": row.strategy,
            "rerank": row.rerank,
            "result_count": row.result_count,
            "latency_ms": row.latency_ms,
            "job_id": row.job_id,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


@router.get("/search/queries/{query_id}")
def search_snapshot(query_id: int, db: DbSession) -> dict:
    row = db.get(SearchQuery, query_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No search query {query_id}.")
    results = db.scalars(
        select(SearchResult)
        .where(SearchResult.search_query_id == query_id)
        .order_by(SearchResult.rank)
    ).all()
    return {
        "id": row.id,
        "raw_query": row.raw_query,
        "parsed": row.parsed,
        "strategy": row.strategy,
        "rerank": row.rerank,
        "result_count": row.result_count,
        "latency_ms": row.latency_ms,
        "created_at": row.created_at.isoformat(),
        "results": [
            {
                "candidate_id": item.candidate_id,
                "rank": item.rank,
                "score": item.score,
                "components": item.components,
            }
            for item in results
        ],
    }
