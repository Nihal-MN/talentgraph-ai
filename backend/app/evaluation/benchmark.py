"""Benchmark runner — compares retrieval strategies on the golden set and
persists runs so the Evaluation page shows actual measured numbers.

Strategies compared (each runs the REAL pipeline, filters included):
  lexical       — FTS/BM25 only, no rerank
  vector        — embeddings only, no rerank
  hybrid        — RRF fusion of lexical + vector, no rerank
  hybrid_rerank — RRF fusion + the deterministic feature reranker
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.evaluation.golden import GOLDEN_QUERIES, build_facts
from app.evaluation.metrics import evaluate_ranking
from app.models import BenchmarkRun, Candidate, Skill
from app.services.search_service import SearchRequest, run_search

STRATEGY_RUNS: dict[str, tuple[str, bool]] = {
    "lexical": ("lexical", False),
    "vector": ("vector", False),
    "hybrid": ("hybrid", False),
    "hybrid_rerank": ("hybrid", True),
}

RETRIEVAL_DEPTH = 50  # candidates per query per strategy (metrics truncate to k)


def _load_facts(db: Session) -> dict[int, dict]:
    candidates = db.scalars(
        select(Candidate).options(
            selectinload(Candidate.skills).selectinload(Skill.normalized_skill),
            joinedload(Candidate.location),
            joinedload(Candidate.industry),
        )
    ).all()
    return {candidate.id: build_facts(candidate) for candidate in candidates}


def run_benchmark(
    db: Session,
    k: int = 10,
    persist: bool = False,
    strategy_keys: list[str] | None = None,
) -> dict:
    started = time.perf_counter()
    facts = _load_facts(db)
    keys = strategy_keys or list(STRATEGY_RUNS.keys())

    aggregated: dict[str, dict] = {}
    per_query: list[dict] = []

    for strategy_key in keys:
        base_strategy, use_rerank = STRATEGY_RUNS[strategy_key]
        metric_accumulator: dict[str, list[float]] = {
            "precision_at_k": [],
            "recall_at_k": [],
            "mrr": [],
            "ndcg_at_k": [],
        }
        for golden in GOLDEN_QUERIES:
            outcome = run_search(
                db,
                SearchRequest(
                    raw_query=golden.query,
                    filters=golden.filters or {},
                    strategy=base_strategy,
                    limit=RETRIEVAL_DEPTH,
                    rerank=use_rerank,
                    log=False,
                ),
            )
            ranked_ids = [result["id"] for result in outcome["results"]]
            retrieved_grades = [golden.rel(facts[candidate_id]) for candidate_id in ranked_ids]
            ideal_grades = [golden.rel(f) for f in facts.values()]
            metrics = evaluate_ranking(retrieved_grades, ideal_grades, k)
            for metric, value in metrics.items():
                if metric in metric_accumulator:
                    metric_accumulator[metric].append(value)
            per_query.append(
                {
                    "query_id": golden.id,
                    "query": golden.query,
                    "strategy": strategy_key,
                    "top_ids": ranked_ids[:k],
                    "top_grades": retrieved_grades[:k],
                    "metrics": metrics,
                    "latency_ms": outcome["took_ms"],
                }
            )
        aggregated[strategy_key] = {
            metric: round(sum(values) / len(values), 4) if values else 0.0
            for metric, values in metric_accumulator.items()
        }

    duration_ms = int((time.perf_counter() - started) * 1000)
    result = {
        "k": k,
        "dataset_size": len(facts),
        "query_count": len(GOLDEN_QUERIES),
        "strategies": keys,
        "metrics": aggregated,
        "per_query": per_query,
        "duration_ms": duration_ms,
    }

    if persist:
        run = BenchmarkRun(
            k=k,
            strategies=keys,
            dataset_size=len(facts),
            query_count=len(GOLDEN_QUERIES),
            duration_ms=duration_ms,
            metrics=aggregated,
            per_query=per_query,
            created_at=datetime.now(UTC),
        )
        db.add(run)
        db.commit()
        result["benchmark_run_id"] = run.id

    return result


def latest_benchmark(db: Session) -> dict | None:
    run = db.scalars(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc()).limit(1)).first()
    if run is None:
        return None
    return {
        "id": run.id,
        "k": run.k,
        "dataset_size": run.dataset_size,
        "query_count": run.query_count,
        "duration_ms": run.duration_ms,
        "strategies": run.strategies,
        "metrics": run.metrics,
        "per_query": run.per_query,
        "created_at": run.created_at.isoformat(),
    }
