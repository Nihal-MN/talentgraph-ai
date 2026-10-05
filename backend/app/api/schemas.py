"""API request/response schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class FiltersIn(BaseModel):
    skills: list[str] | None = None
    min_years: float | None = Field(default=None, ge=0, le=50)
    max_years: float | None = Field(default=None, ge=0, le=50)
    seniority: list[str] | None = None
    cities: list[str] | None = None
    countries: list[str] | None = None
    region: str | None = None
    industry: str | None = None
    family: str | None = None


class SearchIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    filters: FiltersIn | None = None
    strategy: Literal["lexical", "vector", "hybrid"] = "hybrid"
    limit: int = Field(default=20, ge=1, le=100)
    rerank: bool = True


class SavedSearchIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=500)
    query: dict


class IngestIn(BaseModel):
    resume_text: str = Field(min_length=30, max_length=20000)
    full_name: str | None = Field(default=None, max_length=160)


class RediscoveryIn(BaseModel):
    jd_text: str = Field(min_length=40, max_length=20000)
    title: str | None = Field(default=None, max_length=220)
    company_name: str | None = Field(default=None, max_length=160)
    limit: int = Field(default=15, ge=1, le=50)


class BenchmarkIn(BaseModel):
    k: int = Field(default=10, ge=1, le=50)
    strategies: list[Literal["lexical", "vector", "hybrid", "hybrid_rerank"]] | None = None
