"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import candidates, evaluation, health, rediscovery, saved, search
from app.core.config import get_settings
from app.core.errors import AppError


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Open-source semantic talent search and candidate rediscovery engine — "
            "structured filters, lexical + vector retrieval, hybrid fusion, reranking, "
            "and measurable retrieval quality."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={
                "error": {"code": exc.code.value, "message": exc.message, "detail": exc.detail}
            },
        )

    app.include_router(health.router, prefix="/api/v1", tags=["system"])
    app.include_router(search.router, prefix="/api/v1", tags=["search"])
    app.include_router(candidates.router, prefix="/api/v1", tags=["candidates"])
    app.include_router(saved.router, prefix="/api/v1", tags=["saved searches"])
    app.include_router(rediscovery.router, prefix="/api/v1", tags=["rediscovery"])
    app.include_router(evaluation.router, prefix="/api/v1", tags=["evaluation"])

    return app


app = create_app()
