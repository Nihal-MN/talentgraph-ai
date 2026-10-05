"""Search-side entities: SearchQuery (log/analytics), SearchResult (snapshot +
evidence), SavedSearch, and the operational BenchmarkRun table."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class SearchQuery(Base, TimestampMixin):
    __tablename__ = "search_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_query: Mapped[str] = mapped_column(Text)
    parsed: Mapped[dict | None] = mapped_column(JSON)  # ParsedQuery dump
    strategy: Mapped[str] = mapped_column(String(20))  # lexical | vector | hybrid
    rerank: Mapped[bool] = mapped_column(Boolean, default=False)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # set for rediscovery runs

    results: Mapped[list[SearchResult]] = relationship(
        back_populates="search_query", cascade="all, delete-orphan"
    )


class SearchResult(Base, TimestampMixin):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    search_query_id: Mapped[int] = mapped_column(ForeignKey("search_queries.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    # {"lexical": {rank, score, matched_terms} | None,
    #  "vector":  {rank, similarity} | None,
    #  "fusion":  {score}, "rerank": {score, notes} | None,
    #  "why": {matched_skills, evidence, filters}}
    components: Mapped[dict | None] = mapped_column(JSON)

    search_query: Mapped[SearchQuery] = relationship(back_populates="results")


class SavedSearch(Base, TimestampMixin):
    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    query: Mapped[dict] = mapped_column(JSON)  # raw + filters + strategy + rerank
    run_count: Mapped[int] = mapped_column(Integer, default=0)
    last_run_at: Mapped[datetime | None] = mapped_column()


class BenchmarkRun(Base):
    """Operational table (beyond the 13 core entities) storing evaluation runs
    so the Evaluation page can show the latest actual metrics without recomputing."""

    __tablename__ = "benchmark_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    k: Mapped[int] = mapped_column(Integer)
    strategies: Mapped[list | None] = mapped_column(JSON)
    dataset_size: Mapped[int] = mapped_column(Integer)
    query_count: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # {"lexical": {p_at_k, r_at_k, mrr, ndcg, ...}, "vector": {...}, ...}
    metrics: Mapped[dict | None] = mapped_column(JSON)
    per_query: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column()
