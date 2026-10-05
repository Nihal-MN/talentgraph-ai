"""Application settings — environment-driven with safe, keyless defaults.

The whole product runs WITHOUT any API key: embeddings fall back to a
deterministic demo embedder and query parsing falls back to a rule-based
parser. With ``OPENAI_API_KEY`` set, ``AI_PROVIDER=auto`` switches to live
embeddings + LLM parsing. The active mode is always reported by /health.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── core ─────────────────────────────────────────────────────────────
    app_name: str = "TalentGraph AI"
    debug: bool = False
    database_url: str = ""  # default resolved below (SQLite dev fallback)
    cors_origins: str = "http://localhost:3000,http://localhost:3400"

    # ── AI provider ──────────────────────────────────────────────────────
    # auto → OpenAI when OPENAI_API_KEY is set, deterministic demo mode otherwise
    ai_provider: str = "auto"  # auto | demo | openai
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-5.6-terra"

    # Embedding dimensionality used for the vector column. Demo embedder
    # produces this size; when switching to OpenAI either keep this size
    # (passed as `dimensions` for text-embedding-3 family) or set 1536 and
    # re-embed (`make reembed`).
    embedding_dims: int = 384

    # ── retrieval defaults ───────────────────────────────────────────────
    rrf_k: int = 60
    default_strategy: str = "hybrid"  # lexical | vector | hybrid
    default_limit: int = 20
    max_limit: int = 100
    rerank_default: bool = True
    vector_hnsw: bool = True  # create pgvector index when supported

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return "sqlite:///./talentgraph-dev.db"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def resolved_ai_mode(self) -> str:
        """'demo' or 'openai' — what will actually run, given the config."""
        if self.ai_provider == "openai":
            return "openai"
        if self.ai_provider == "demo":
            return "demo"
        return "openai" if self.openai_api_key else "demo"


@lru_cache
def get_settings() -> Settings:
    return Settings()
