"""Embeddings behind a provider adapter.

- ``DemoEmbedder`` — a deterministic, dependency-free *lexical-semantic* embedder:
  feature-hashed bag of tokens + taxonomy-canonicalized concepts + related-skill
  expansion, L2-normalized. It makes keyless demo semantic search genuinely work
  (e.g. query "k8s" lands near profiles written as "Kubernetes") without ever
  claiming to be a neural model — the UI and docs label it honestly.
- ``OpenAIEmbedder`` — live embeddings (text-embedding-3 family) behind the same
  interface, selected by ``AI_PROVIDER=auto`` when a key exists. Stub-tested.

Both produce vectors of ``settings.embedding_dims`` (default 384), stored via
the portable VectorType (pgvector on PostgreSQL, JSON on SQLite).
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.services.normalize import canonical_for, tokenize
from app.services.taxonomy import SKILLS

EMBED_BATCH_SIZE = 64
OPENAI_NATIVE_DIMS = {"text-embedding-3-small": 1536, "text-embedding-3-large": 3072}


class EmbeddingProvider(Protocol):
    name: str
    dims: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DemoEmbedder:
    """Deterministic feature-hash embedder with taxonomy expansion."""

    name = "demo-lexical-semantic-v1"

    def __init__(self, dims: int = 384) -> None:
        self.dims = dims

    def _embed_one(self, text: str) -> list[float]:
        features: defaultdict[str, float] = defaultdict(float)
        for token in tokenize(text):
            features[token] += 1.0
            canonical = canonical_for(token)
            if canonical:
                features[canonical] += 2.0
                for related in SKILLS.get(canonical, {}).get("related", []):
                    features[related.lower()] += 0.6
        vector = [0.0] * self.dims
        for feature, weight in features.items():
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "little") % self.dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += weight * sign
            index2 = int.from_bytes(digest[4:8], "little") % self.dims
            vector[index2] += weight * sign * 0.5
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]


class OpenAIEmbedder:
    """Live embeddings adapter (stub-tested; used when a key is configured)."""

    def __init__(self, client, model: str, dims: int) -> None:
        self._client = client
        self.name = model
        self.model = model
        self.dims = dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            kwargs: dict = {"model": self.model, "input": batch}
            native = OPENAI_NATIVE_DIMS.get(self.model)
            if native is not None and self.dims != native:
                kwargs["dimensions"] = self.dims
            try:
                response = self._client.embeddings.create(**kwargs)
            except Exception as exc:  # noqa: BLE001 — provider failures are typed
                raise AppError(
                    ErrorCode.provider_unavailable,
                    f"Embedding provider failed: {exc}",
                ) from exc
            ordered = sorted(response.data, key=lambda item: item.index)
            vectors.extend([list(item.embedding) for item in ordered])
        return vectors


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.resolved_ai_mode == "openai":
        from openai import OpenAI

        if not settings.openai_api_key:
            raise AppError(
                ErrorCode.provider_unavailable,
                "OpenAI embeddings selected but OPENAI_API_KEY is not set.",
            )
        client = OpenAI(api_key=settings.openai_api_key)
        return OpenAIEmbedder(client, settings.openai_embedding_model, settings.embedding_dims)
    return DemoEmbedder(dims=settings.embedding_dims)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def embedding_document(parts: dict) -> str:
    """The canonical text embedded for a candidate (kept in one place so
    re-embedding decisions are explainable and hashable)."""
    pieces = [
        parts.get("headline") or "",
        parts.get("seniority") or "",
        " ".join(parts.get("skills") or []),
        parts.get("summary") or "",
        parts.get("resume_text") or "",
    ]
    return "\n".join(piece for piece in pieces if piece)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
