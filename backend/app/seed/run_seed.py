"""Seed runner — ``python -m app.seed [--count N] [--reset] [--reembed]``.

Builds the deterministic synthetic dataset (default 200 profiles), reference
entities (industries, locations, companies), the normalized-skill table,
search text + embeddings for every candidate, example saved searches and
example jobs — then optionally runs the retrieval benchmark once so the
Evaluation page has real numbers from the first boot.
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import (
    BenchmarkRun,
    Candidate,
    Company,
    Education,
    EmbeddingMetadata,
    Experience,
    Industry,
    Job,
    Location,
    NormalizedSkill,
    SavedSearch,
    SearchQuery,
    SearchResult,
    Skill,
)
from app.seed.generator import HOSTILE_RESUME_LINE, generate_candidates, generate_companies
from app.services.indexing import build_search_text


def _clear_all(db: Session) -> None:
    for model in (
        SearchResult,
        SearchQuery,
        BenchmarkRun,
        SavedSearch,
        EmbeddingMetadata,
        Skill,
        Experience,
        Education,
        Candidate,
        Company,
        NormalizedSkill,
        Job,
        Location,
        Industry,
    ):
        db.query(model).delete()
    db.commit()


def seed(db: Session, count: int = 200, with_benchmark: bool = True) -> dict:
    from app.services.embedding import get_embedding_provider
    from app.services.normalize import normalize_title
    from app.services.taxonomy import INDUSTRIES, SKILLS

    started = time.perf_counter()

    # ── normalized skills (taxonomy → DB) ────────────────────────────────
    skill_rows: dict[str, NormalizedSkill] = {}
    for canonical, meta in SKILLS.items():
        row = NormalizedSkill(
            canonical_name=canonical,
            category=meta.get("category"),
            aliases=meta.get("aliases", []),
            related=meta.get("related", []),
        )
        db.add(row)
        skill_rows[canonical] = row
    db.flush()

    # ── industries ───────────────────────────────────────────────────────
    industry_rows: dict[str, Industry] = {}
    for name in INDUSTRIES:
        row = Industry(name=name)
        db.add(row)
        industry_rows[name] = row
    db.flush()

    # ── candidates ───────────────────────────────────────────────────────
    dataset = generate_candidates(count=count)
    company_data = generate_companies(dataset)
    provider = get_embedding_provider()

    # locations + companies on demand
    location_rows: dict[str, Location] = {}
    company_rows: dict[str, Company] = {}

    def get_location(city: str, country: str, region: str) -> Location:
        key = f"{city}|{country}"
        if key not in location_rows:
            row = Location(city=city, country=country, region=region)
            db.add(row)
            db.flush()
            location_rows[key] = row
        return location_rows[key]

    for company in company_data:
        row = Company(
            name=company["name"],
            industry_id=industry_rows.get(company["industry"]).id
            if company["industry"] in industry_rows
            else None,
            hq_location=company["hq_location"],
            size=company["size"],
        )
        db.add(row)
        company_rows[company["name"]] = row
    db.flush()

    candidate_rows: list[Candidate] = []

    for item in dataset:
        location = get_location(item["city"], item["country"], item["region"])
        candidate = Candidate(
            full_name=item["full_name"],
            headline=item["headline"],
            seniority=item["seniority"],
            years_experience=item["years_experience"],
            summary=item["summary"],
            resume_text=item["resume_text"],
            location_id=location.id,
            industry_id=industry_rows[item["industry"]].id
            if item["industry"] in industry_rows
            else None,
            is_synthetic=True,
            source="seed",
        )
        db.add(candidate)
        db.flush()
        candidate_rows.append(candidate)

        for order, role in enumerate(reversed(item["experiences"])):
            normalized = normalize_title(role["title"])
            db.add(
                Experience(
                    candidate_id=candidate.id,
                    title=role["title"],
                    normalized_title=normalized["normalized_title"],
                    company_id=company_rows[role["company"]].id
                    if role["company"] in company_rows
                    else None,
                    start_date=date(role["start_year"], 1, 1),
                    end_date=None
                    if role["is_current"]
                    else date(role["end_year"] or role["start_year"] + 1, 1, 1),
                    is_current=role["is_current"],
                    sort_order=order,
                )
            )

        for skill in item["skills"]:
            normalized = skill_rows.get(skill["canonical"])
            db.add(
                Skill(
                    candidate_id=candidate.id,
                    name_raw=skill["raw"],
                    normalized_skill_id=normalized.id if normalized else None,
                    category=normalized.category if normalized else None,
                    evidence=skill["evidence"],
                )
            )

        db.add(
            Education(
                candidate_id=candidate.id,
                degree=f"{item['education']['degree']} {item['education']['field']}",
                institution=item["education"]["institution"],
                field=item["education"]["field"],
                year=item["education"]["year"],
            )
        )
    db.flush()

    # ── search text + embeddings (batched for provider efficiency) ───────
    for candidate in candidate_rows:
        candidate.search_text = build_search_text(
            candidate, [skill.name_raw for skill in candidate.skills]
        )
    db.flush()

    from app.services.embedding import content_hash, embedding_document

    documents = []
    for candidate in candidate_rows:
        documents.append(
            embedding_document(
                {
                    "headline": candidate.headline,
                    "seniority": candidate.seniority,
                    "skills": [skill.name_raw for skill in candidate.skills],
                    "summary": candidate.summary,
                    "resume_text": candidate.resume_text,
                }
            )
        )

    from app.models import EmbeddingMetadata

    now = datetime.now(tz=None).astimezone()
    vectors = provider.embed(documents)
    for candidate, document, vector in zip(candidate_rows, documents, vectors, strict=True):
        db.add(
            EmbeddingMetadata(
                candidate_id=candidate.id,
                model_name=provider.name,
                dimensions=provider.dims,
                content_hash=content_hash(document),
                embedded_at=now,
                embedding=vector,
            )
        )
    db.flush()

    # ── example saved searches + jobs ────────────────────────────────────
    db.add(
        SavedSearch(
            name="Senior Python backend in Europe",
            description="Backend engineers, 5+ years, Python, located in Europe.",
            query={
                "raw": "senior python backend engineer with 5+ years in Europe",
                "filters": {"skills": ["python"], "min_years": 5, "region": "Europe"},
                "strategy": "hybrid",
                "rerank": True,
            },
            run_count=0,
        )
    )
    db.add(
        SavedSearch(
            name="Data engineers — GCC",
            description="Data engineering stack across the Gulf region.",
            query={
                "raw": "data engineer with spark and airflow in the Gulf",
                "filters": {"region": "MENA", "skills": ["spark"]},
                "strategy": "hybrid",
                "rerank": True,
            },
            run_count=0,
        )
    )
    db.add(
        Job(
            title="Senior Backend Engineer",
            company_name="Example Freight Co",
            description_text=(
                "We are hiring a Senior Backend Engineer (5+ years) to build "
                "Python/FastAPI services for our logistics platform. You will work "
                "with PostgreSQL, Redis and Docker, and own services end to end. "
                "Nice to have: Kubernetes, Kafka, AWS."
            ),
            parsed={
                "skills": [
                    "python",
                    "fastapi",
                    "postgresql",
                    "redis",
                    "docker",
                    "kubernetes",
                    "kafka",
                    "aws",
                ],
                "min_years": 5,
                "seniority": "senior",
                "domains": ["Logistics"],
                "location": None,
                "title_family": "backend engineer",
            },
            source="seed",
        )
    )
    db.add(
        Job(
            title="Machine Learning Engineer (LLM/RAG)",
            company_name="Example Health AI",
            description_text=(
                "Join our applied AI team to build retrieval-augmented generation "
                "systems. You will work with embeddings, vector databases and LLM "
                "APIs, shipping NLP features with PyTorch. 3+ years of production ML."
            ),
            parsed={
                "skills": [
                    "python",
                    "pytorch",
                    "nlp",
                    "llm",
                    "rag",
                    "embeddings",
                    "vector database",
                ],
                "min_years": 3,
                "seniority": None,
                "domains": ["Healthtech"],
                "location": None,
                "title_family": "ml engineer",
            },
            source="seed",
        )
    )
    db.commit()

    summary = {
        "candidates": db.scalar(select(func.count()).select_from(Candidate)),
        "companies": db.scalar(select(func.count()).select_from(Company)),
        "skills": db.scalar(select(func.count()).select_from(Skill)),
        "normalized_skills": db.scalar(select(func.count()).select_from(NormalizedSkill)),
        "embeddings": db.scalar(select(func.count()).select_from(EmbeddingMetadata)),
        "provider": provider.name,
        "dims": provider.dims,
        "elapsed_s": round(time.perf_counter() - started, 2),
        "hostile_example": HOSTILE_RESUME_LINE[:60] + "...",
    }

    if with_benchmark:
        from app.evaluation.benchmark import run_benchmark

        benchmark = run_benchmark(db, k=10, persist=True)
        summary["benchmark"] = {
            strategy: {metric: round(value, 3) for metric, value in metrics.items()}
            for strategy, metrics in benchmark["metrics"].items()
        }

    return summary


def reembed(db: Session) -> dict:
    """Recompute embeddings for every candidate with the current provider."""
    from app.services.indexing import index_candidate

    candidates = db.scalars(select(Candidate)).all()
    for candidate in candidates:
        index_candidate(db, candidate, force=True)
    db.commit()
    return {"reembedded": len(candidates)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the TalentGraph AI demo dataset")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--reset", action="store_true", help="delete existing data first")
    parser.add_argument("--reembed", action="store_true", help="recompute embeddings only")
    parser.add_argument("--no-benchmark", action="store_true")
    args = parser.parse_args()

    with SessionLocal() as db:
        if args.reembed:
            result = reembed(db)
            print(f"Re-embedded {result['reembedded']} candidates.")
            return
        if args.reset:
            _clear_all(db)
        summary = seed(db, count=args.count, with_benchmark=not args.no_benchmark)
    print("Seeded TalentGraph dataset:")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
