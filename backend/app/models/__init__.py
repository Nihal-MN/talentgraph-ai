"""All models, imported so Alembic and the app see a complete metadata object."""

from app.models.candidate import (
    Candidate,
    Education,
    EmbeddingMetadata,
    Experience,
    NormalizedSkill,
    Skill,
)
from app.models.job import Job
from app.models.refs import Company, Industry, Location
from app.models.search import BenchmarkRun, SavedSearch, SearchQuery, SearchResult

__all__ = [
    "BenchmarkRun",
    "Candidate",
    "Company",
    "Education",
    "EmbeddingMetadata",
    "Experience",
    "Industry",
    "Job",
    "Location",
    "NormalizedSkill",
    "SavedSearch",
    "SearchQuery",
    "SearchResult",
    "Skill",
]
