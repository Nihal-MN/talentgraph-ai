"""Reference entities: Industry, Location, Company."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate, Experience


class Industry(Base, TimestampMixin):
    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)

    candidates: Mapped[list[Candidate]] = relationship(back_populates="industry")


class Location(Base, TimestampMixin):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("city", "country", name="uq_location_city_country"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(120))
    region: Mapped[str | None] = mapped_column(String(120))

    candidates: Mapped[list[Candidate]] = relationship(back_populates="location")

    @property
    def label(self) -> str:
        return f"{self.city}, {self.country}"


class Company(Base, TimestampMixin):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    industry_id: Mapped[int | None] = mapped_column(ForeignKey("industries.id"))
    hq_location: Mapped[str | None] = mapped_column(String(160))
    size: Mapped[str | None] = mapped_column(String(40))  # e.g. "50-200"
    description: Mapped[str | None] = mapped_column(Text)

    industry: Mapped[Industry | None] = relationship()
    experiences: Mapped[list[Experience]] = relationship(back_populates="company")
