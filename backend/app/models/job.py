"""Job entity — created from pasted JD text, used by Talent Rediscovery."""

from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(220))
    company_name: Mapped[str | None] = mapped_column(String(160))
    description_text: Mapped[str] = mapped_column(Text)  # stored source (untrusted data)
    parsed: Mapped[dict | None] = mapped_column(JSON)  # skills, seniority, domain, location, years
    source: Mapped[str] = mapped_column(String(20), default="paste")  # paste | seed
    status: Mapped[str] = mapped_column(String(20), default="open")
