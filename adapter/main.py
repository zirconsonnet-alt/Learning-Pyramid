from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from adapter.errors import register_exception_handlers
from adapter.routers import asr, layers, learning_tasks, materials, media, projects, push, review, validation
from backend.system.runtime_env import resource_root
from backend.system.version import APP_NAME, APP_VERSION


def _frontend_dist_dir() -> Path:
    return resource_root() / "frontend" / "dist"


def _resolve_frontend_file(dist_dir: Path, full_path: str) -> Path | None:
    rel = full_path.lstrip("/")
    if not rel:
        return dist_dir / "index.html"
    candidate = (dist_dir / rel).resolve()
    try:
        candidate.relative_to(dist_dir.resolve())
    except Exception:
        return None
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{APP_NAME} API",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(projects.router, prefix="/api", tags=["projects"])
    app.include_router(materials.router, prefix="/api", tags=["materials"])
    app.include_router(media.router, prefix="/api", tags=["media"])
    app.include_router(learning_tasks.router, prefix="/api", tags=["learning-tasks"])
    app.include_router(review.router, prefix="/api", tags=["review"])
    app.include_router(layers.router, prefix="/api", tags=["layers"])
    app.include_router(push.router, prefix="/api", tags=["push"])
    app.include_router(validation.router, prefix="/api", tags=["validation"])
    app.include_router(asr.router, prefix="/api", tags=["asr"])

    @app.get("/api/health")
    def health() -> dict:
        return {
            "ok": True,
            "data": {
                "status": "ok",
                "app": APP_NAME,
                "version": APP_VERSION,
                "runtimeMode": os.getenv("PLM_RUNTIME_MODE", "unknown"),
            },
        }

    dist_dir = _frontend_dist_dir()
    index_file = dist_dir / "index.html"

    @app.get("/", include_in_schema=False)
    def serve_frontend_root():
        if index_file.exists():
            return FileResponse(str(index_file))
        return PlainTextResponse(f"{APP_NAME} frontend build is missing. Build frontend/dist before starting release mode.", status_code=503)

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str):
        if not index_file.exists():
            return PlainTextResponse(f"{APP_NAME} frontend build is missing. Build frontend/dist before starting release mode.", status_code=503)

        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        file_path = _resolve_frontend_file(dist_dir, full_path)
        if file_path is not None:
            return FileResponse(str(file_path))

        if "." in Path(full_path).name:
            return PlainTextResponse("Not found", status_code=404)
        return FileResponse(str(index_file))

    return app


app = create_app()
