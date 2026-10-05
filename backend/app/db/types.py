"""Portable vector column type.

- PostgreSQL: native ``pgvector`` column (vector(384) by default) — cosine
  operator ``<=>`` and HNSW indexes available.
- Everything else (SQLite dev fallback / hermetic tests): stored as JSON text,
  with similarity computed in Python by the retrieval services.

This keeps one migration path for both worlds and lets the whole test suite
run without Docker, while the demo/acceptance stack exercises real pgvector.
"""

from __future__ import annotations

import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class VectorType(TypeDecorator):
    """A list[float] that maps to pgvector on PostgreSQL and JSON on SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, dims: int = 384) -> None:
        super().__init__()
        self.dims = dims

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(self.dims))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        floats = [float(v) for v in value]
        if dialect.name == "postgresql":
            return floats
        return json.dumps(floats)

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if dialect.name == "postgresql":
            return [float(v) for v in value]
        return [float(v) for v in json.loads(value)]

    @property
    def python_type(self) -> type:
        return list
