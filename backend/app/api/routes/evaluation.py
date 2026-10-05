"""Evaluation endpoints — benchmark runs and analytics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.api.schemas import BenchmarkIn
from app.evaluation.benchmark import latest_benchmark, run_benchmark

router = APIRouter()


@router.get("/evaluation/benchmark")
def get_benchmark(db: DbSession) -> dict:
    stored = latest_benchmark(db)
    if stored is not None:
        return stored
    # no stored run yet — compute one on the fly (not persisted)
    return run_benchmark(db, k=10, persist=False)


@router.post("/evaluation/run", status_code=201)
def run_evaluation(payload: BenchmarkIn, db: DbSession) -> dict:
    result = run_benchmark(db, k=payload.k, persist=True, strategy_keys=payload.strategies)
    if not result.get("metrics"):
        raise HTTPException(status_code=409, detail="No candidates with embeddings — seed first.")
    return result
