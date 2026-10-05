"""Saved searches: create, list, reopen (re-run), delete."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.api.schemas import SavedSearchIn
from app.models import SavedSearch
from app.services.search_service import SearchRequest, run_search

router = APIRouter()


@router.get("/saved-searches")
def list_saved(db: DbSession) -> list[dict]:
    rows = db.scalars(select(SavedSearch).order_by(SavedSearch.created_at.desc())).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "query": row.query,
            "run_count": row.run_count,
            "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        }
        for row in rows
    ]


@router.post("/saved-searches", status_code=201)
def create_saved(payload: SavedSearchIn, db: DbSession) -> dict:
    row = SavedSearch(name=payload.name, description=payload.description, query=payload.query)
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, "query": row.query}


@router.post("/saved-searches/{saved_id}/run")
def run_saved(saved_id: int, db: DbSession) -> dict:
    row = db.get(SavedSearch, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No saved search {saved_id}.")
    query = row.query or {}
    outcome = run_search(
        db,
        SearchRequest(
            raw_query=query.get("raw", ""),
            filters=query.get("filters") or {},
            strategy=query.get("strategy", "hybrid"),
            limit=query.get("limit", 20),
            rerank=query.get("rerank", True),
        ),
    )
    row.run_count += 1
    row.last_run_at = datetime.now(UTC)
    db.commit()
    return {"saved_search": {"id": row.id, "name": row.name, "run_count": row.run_count}, **outcome}


@router.delete("/saved-searches/{saved_id}", status_code=204)
def delete_saved(saved_id: int, db: DbSession) -> None:
    row = db.get(SavedSearch, saved_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"No saved search {saved_id}.")
    db.delete(row)
    db.commit()
