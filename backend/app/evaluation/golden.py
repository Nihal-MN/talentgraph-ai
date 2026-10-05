"""Golden evaluation set — 20 queries with deterministic relevance labels.

Honest design note (also in docs/EVALUATION.md): this is a *synthetic-IR eval*.
Relevance labels are predicates over the generator's ground-truth fields, not
human judgments — they measure retrieval mechanics (exactness, synonym
handling, filter correctness, fusion quality) reproducibly. That is exactly
what the benchmark claims to measure, no more.

Grades: 2 = ideal, 1 = acceptable, 0 = irrelevant.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.models import Candidate
from app.services.normalize import normalize_title


@dataclass
class GoldenQuery:
    id: str
    query: str
    rel: Callable[[dict], int]
    filters: dict | None = None  # explicit filters merged like the UI would


def build_facts(candidate: Candidate) -> dict:
    skills = set()
    for skill in candidate.skills:
        canonical = (
            skill.normalized_skill.canonical_name
            if skill.normalized_skill
            else skill.name_raw.lower()
        )
        skills.add(canonical)
    return {
        "id": candidate.id,
        "skills": skills,
        "years": candidate.years_experience or 0.0,
        "seniority": candidate.seniority or "",
        "city": candidate.location.city if candidate.location else "",
        "country": candidate.location.country if candidate.location else "",
        "region": candidate.location.region if candidate.location else "",
        "industry": candidate.industry.name if candidate.industry else "",
        "headline": (candidate.headline or "").lower(),
        "family": normalize_title(candidate.headline or "").get("family") or "",
    }


def _has(facts: dict, *skills: str) -> bool:
    return all(skill in facts["skills"] for skill in skills)


def _any(facts: dict, *skills: str) -> bool:
    return any(skill in facts["skills"] for skill in skills)


ANY_FAMILY = {
    "backend": ("backend engineer", "fullstack engineer"),
    "frontend": ("frontend engineer", "fullstack engineer"),
    "data": ("data engineer", "data scientist", "data analyst"),
    "ml": ("ml engineer", "data scientist"),
}


GOLDEN_QUERIES: list[GoldenQuery] = [
    GoldenQuery(
        "q01",
        "python backend engineer with 5+ years of experience",
        lambda f: (
            2
            if f["family"] in ANY_FAMILY["backend"] and _has(f, "python") and f["years"] >= 5
            else (
                1
                if f["family"] in ANY_FAMILY["backend"] and _has(f, "python") and f["years"] >= 3
                else 0
            )
        ),
    ),
    GoldenQuery(
        "q02",
        "kubernetes engineer",
        lambda f: (
            2
            if _has(f, "kubernetes") and f["family"].endswith("engineer")
            else (1 if _has(f, "kubernetes") else 0)
        ),
    ),
    GoldenQuery(
        "q03",
        "backend engineers in Dubai",
        lambda f: (
            2
            if f["city"] == "Dubai" and f["family"] in ANY_FAMILY["backend"]
            else (
                1
                if f["city"] == "Dubai"
                and (_any(f, "python", "java", "go", "nodejs", "django", "fastapi"))
                else 0
            )
        ),
    ),
    GoldenQuery(
        "q04",
        "data scientist in Germany with experimentation experience",
        lambda f: (
            2
            if f["country"] == "Germany"
            and _has(f, "a-b-testing")
            and f["family"] in ("data scientist", "data analyst")
            else (
                1
                if f["country"] == "Germany"
                and _any(f, "statistics", "machine-learning", "a-b-testing")
                else 0
            )
        ),
    ),
    GoldenQuery(
        "q05",
        "frontend developer with react and typescript",
        lambda f: (
            2
            if f["family"] in ANY_FAMILY["frontend"] and _has(f, "react", "typescript")
            else (1 if _any(f, "react", "typescript") and f["family"].endswith("engineer") else 0)
        ),
    ),
    GoldenQuery(
        "q06",
        "data engineer with spark and airflow",
        lambda f: (
            2
            if _has(f, "spark", "airflow")
            else (1 if _any(f, "spark", "airflow", "etl", "kafka") else 0)
        ),
    ),
    GoldenQuery(
        "q07",
        "machine learning engineer with pytorch and nlp experience",
        lambda f: (
            2
            if f["family"] in ANY_FAMILY["ml"] and _has(f, "pytorch") and _any(f, "nlp", "llm")
            else (
                1
                if _has(f, "pytorch") or (_has(f, "machine-learning") and _any(f, "nlp", "llm"))
                else 0
            )
        ),
    ),
    GoldenQuery(
        "q08",
        "devops engineer with terraform and kubernetes",
        lambda f: (
            2
            if f["family"] == "devops engineer" and _has(f, "terraform", "kubernetes")
            else (1 if _has(f, "terraform") or _has(f, "kubernetes") else 0)
        ),
    ),
    GoldenQuery(
        "q09",
        "fintech backend engineers with payments experience",
        lambda f: (
            2
            if f["industry"] == "Fintech" and f["family"] in ANY_FAMILY["backend"]
            else (1 if f["industry"] == "Fintech" or _has(f, "python", "java", "go") else 0)
        ),
    ),
    GoldenQuery(
        "q10",
        "staff level backend engineer",
        lambda f: (
            2
            if f["seniority"] in ("staff", "lead", "head") and f["family"] in ANY_FAMILY["backend"]
            else (1 if f["seniority"] == "senior" and f["family"] in ANY_FAMILY["backend"] else 0)
        ),
    ),
    GoldenQuery(
        "q11",
        "senior python engineer in Berlin with kubernetes",
        lambda f: (
            2
            if f["city"] == "Berlin"
            and _has(f, "python")
            and f["years"] >= 5
            and _any(f, "kubernetes", "docker")
            else (1 if f["city"] == "Berlin" and _has(f, "python") else 0)
        ),
    ),
    GoldenQuery(
        "q12",
        "technical recruiter for engineering teams in the Gulf",
        lambda f: (
            2
            if f["family"] == "recruiter" and f["region"] == "MENA"
            else (1 if f["family"] == "recruiter" or _has(f, "recruiting") else 0)
        ),
    ),
    GoldenQuery(
        "q13",
        "product manager with B2B SaaS experience",
        lambda f: (
            2
            if f["family"] == "product manager" and f["industry"] == "SaaS"
            else (1 if f["family"] == "product manager" else 0)
        ),
    ),
    GoldenQuery(
        "q14",
        "supply chain manager with freight and customs experience",
        lambda f: (
            2
            if f["family"] == "operations" and _has(f, "supply-chain")
            else (1 if _has(f, "supply-chain", "operations", "procurement") else 0)
        ),
    ),
    GoldenQuery(
        "q15",
        "security engineer with appsec and compliance background",
        lambda f: (
            2
            if f["family"] == "security engineer" and _any(f, "compliance", "security")
            else (1 if _any(f, "security", "compliance", "audit") else 0)
        ),
    ),
    GoldenQuery(
        "q16",
        "customer success manager for enterprise SaaS",
        lambda f: (
            2
            if f["family"] == "customer success" and f["industry"] in ("SaaS", "Fintech")
            else (1 if f["family"] == "customer success" or _has(f, "customer success") else 0)
        ),
    ),
    GoldenQuery(
        "q17",
        "financial analyst with FP&A and forecasting",
        lambda f: (
            2
            if f["family"] == "finance" and _has(f, "financial-modeling")
            else (1 if _has(f, "financial-modeling", "accounting") else 0)
        ),
    ),
    GoldenQuery(
        "q18",
        "fullstack engineer with node and postgres",
        lambda f: (
            2
            if f["family"] in ("fullstack engineer", "backend engineer")
            and _has(f, "nodejs", "postgresql")
            else (1 if _any(f, "nodejs", "postgresql") else 0)
        ),
    ),
    GoldenQuery(
        "q19",
        "senior frontend engineer in Europe",
        lambda f: (
            2
            if f["region"] == "Europe" and f["family"] in ANY_FAMILY["frontend"] and f["years"] >= 4
            else (1 if f["region"] == "Europe" and f["family"].endswith("engineer") else 0)
        ),
    ),
    GoldenQuery(
        "q20",
        "ml engineer with RAG and vector database experience",
        lambda f: (
            2
            if _has(f, "rag") and _any(f, "vector database", "embeddings")
            else (1 if _any(f, "rag", "embeddings", "llm", "vector database") else 0)
        ),
    ),
    # ── paraphrase / diffuse queries: no hard constraints — pure ranking test ──
    GoldenQuery(
        "q21",
        "engineers who scaled payments infrastructure at high-growth startups",
        lambda f: (
            2
            if f["industry"] == "Fintech"
            and f["family"].endswith("engineer")
            and f["years"] >= 4
            and _any(f, "microservices", "postgresql", "redis", "kubernetes")
            else (1 if f["industry"] == "Fintech" and f["family"].endswith("engineer") else 0)
        ),
    ),
    GoldenQuery(
        "q22",
        "experience building search or recommendation systems with embeddings",
        lambda f: (
            2
            if _any(f, "rag", "embeddings", "vector database")
            else (1 if _any(f, "machine-learning", "nlp", "llm") else 0)
        ),
    ),
    GoldenQuery(
        "q23",
        "someone who can own our whole data stack: pipelines, warehouse and dashboards",
        lambda f: (
            2
            if _has(f, "spark", "airflow") and _any(f, "snowflake", "data warehouse", "dbt")
            else (1 if _any(f, "spark", "airflow", "dbt", "etl", "snowflake") else 0)
        ),
    ),
    GoldenQuery(
        "q24",
        "product-minded fullstack engineer who shipped customer-facing features",
        lambda f: (
            2
            if f["family"] == "fullstack engineer" and _any(f, "react", "typescript")
            else (
                1
                if f["family"] in ("fullstack engineer", "frontend engineer")
                or _any(f, "react", "typescript", "nodejs")
                else 0
            )
        ),
    ),
]
