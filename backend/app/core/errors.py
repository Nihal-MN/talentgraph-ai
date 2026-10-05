"""Explicit error model shared by services and the API."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    entity_not_found = "entity_not_found"
    validation_error = "validation_error"
    provider_unavailable = "provider_unavailable"
    embedding_missing = "embedding_missing"
    ingestion_failed = "ingestion_failed"
    search_failed = "search_failed"
    policy_blocked = "policy_blocked"


class AppError(Exception):
    """Raised by services to produce a structured error response."""

    HTTP_STATUS = {
        ErrorCode.entity_not_found: 404,
        ErrorCode.validation_error: 422,
        ErrorCode.provider_unavailable: 503,
        ErrorCode.embedding_missing: 409,
        ErrorCode.ingestion_failed: 422,
        ErrorCode.search_failed: 500,
        ErrorCode.policy_blocked: 403,
    }

    def __init__(self, code: ErrorCode, message: str, detail: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    @property
    def http_status(self) -> int:
        return self.HTTP_STATUS.get(self.code, 500)
