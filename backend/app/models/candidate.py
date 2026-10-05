"""Candidate-side entities: Candidate, Experience, Skill, NormalizedSkill,
Education, and the candidate embedding metadata (EmbeddingMetadata)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.db.types import VectorType
from app.models.refs import Company, Industry, Location


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    headline: Mapped[str | None] = mapped_column(String(220))
    seniority: Mapped[str | None] = mapped_column(
        String(40)
    )  # junior|mid|senior|lead|principal|staff
    years_experience: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)
    resume_text: Mapped[str | None] = mapped_column(Text)  # stored source (untrusted data)
    # Denormalized search surface (headline + summary + skills + roles + resume)
    search_text: Mapped[str | None] = mapped_column(Text)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    industry_id: Mapped[int | None] = mapped_column(ForeignKey("industries.id"))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(20), default="seed")  # seed | ingested

    location: Mapped[Location | None] = relationship(back_populates="candidates")
    industry: Mapped[Industry | None] = relationship(back_populates="candidates")
    experiences: Mapped[list[Experience]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", order_by="Experience.sort_order"
    )
    skills: Mapped[list[Skill]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    educations: Mapped[list[Education]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    embedding: Mapped[EmbeddingMetadata | None] = relationship(
        back_populates="candidate", cascade="all, delete-orphan", uselist=False
    )


class Experience(Base, TimestampMixin):
    __tablename__ = "experiences"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    normalized_title: Mapped[str | None] = mapped_column(
        String(120)
    )  # e.g. "senior backend engineer"
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    candidate: Mapped[Candidate] = relationship(back_populates="experiences")
    company: Mapped[Company | None] = relationship(back_populates="experiences")


class NormalizedSkill(Base, TimestampMixin):
    __tablename__ = "normalized_skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(60))  # language|framework|cloud|...
    aliases: Mapped[list | None] = mapped_column(JSON)
    related: Mapped[list | None] = mapped_column(JSON)  # related canonical skills (expander graph)

    skills: Mapped[list[Skill]] = relationship(back_populates="normalized_skill")


class Skill(Base, TimestampMixin):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    name_raw: Mapped[str] = mapped_column(String(120))  # as written in the profile
    normalized_skill_id: Mapped[int | None] = mapped_column(ForeignKey("normalized_skills.id"))
    category: Mapped[str | None] = mapped_column(String(60))  # denormalized for filtering
    evidence: Mapped[str | None] = mapped_column(Text)  # the line this skill came from
    years_used: Mapped[float | None] = mapped_column(Float)

    candidate: Mapped[Candidate] = relationship(back_populates="skills")
    normalized_skill: Mapped[NormalizedSkill | None] = relationship(back_populates="skills")


class Education(Base, TimestampMixin):
    __tablename__ = "educations"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    degree: Mapped[str] = mapped_column(String(160))
    institution: Mapped[str] = mapped_column(String(200))
    field: Mapped[str | None] = mapped_column(String(160))
    year: Mapped[int | None] = mapped_column(Integer)

    candidate: Mapped[Candidate] = relationship(back_populates="educations")


class EmbeddingMetadata(Base, TimestampMixin):
    """One embedding row per candidate (the vector lives here)."""

    __tablename__ = "candidate_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True, index=True)
    model_name: Mapped[str] = mapped_column(String(120))
    dimensions: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))  # sha256 of embedded text
    embedded_at: Mapped[datetime] = mapped_column()
    embedding: Mapped[list | None] = mapped_column(VectorType(384))

    candidate: Mapped[Candidate] = relationship(back_populates="embedding")
