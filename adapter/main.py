from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from adapter.desktop_agent_janitor import collect_desktop_agent_relay_status
from adapter.auth import auth_error_response, resolve_session_user
from adapter.errors import register_exception_handlers
from adapter.deps import get_auth_store, get_desktop_agent_runtime
from adapter.runtime_status import collect_runtime_status
from adapter.routers import asr, auth, desktop_agents, layers, learning_tasks, materials, media, projects, push, review, system, validation
from backend.system.hosted_deployment_checks import hosted_runtime_warnings, validate_hosted_runtime_or_raise
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.runtime_features import current_runtime_features
from backend.system.sql_backend import current_sql_runtime_config
from backend.system.runtime_env import resource_root
from backend.system.version import APP_NAME, APP_VERSION


def _configure_logging() -> None:
    level_name = (os.getenv("PLM_LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


logger = logging.getLogger("learningpyramid.http")


def _env_non_negative_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except Exception:
        return float(default)
    return 0.0 if value <= 0 else float(value)


def _desktop_agent_janitor_interval_seconds() -> float:
    return _env_non_negative_float("PLM_AGENT_JANITOR_INTERVAL_SECONDS", 15.0)


async def _desktop_agent_janitor_loop(stop_event: asyncio.Event, interval_seconds: float) -> None:
    while not stop_event.is_set():
        try:
            report = await asyncio.to_thread(
                collect_desktop_agent_relay_status,
                runtime=get_desktop_agent_runtime(),
                auth_store=get_auth_store(),
                dispatch_alert_webhooks=True,
            )
            expired_streams = len(report.get("expiredStreamIds", ()))
            expired_probes = len(report.get("expiredProbeIds", ()))
            expired_hls_jobs = len(report.get("expiredHlsJobIds", ()))
            pruned_cache = int(report.get("hlsCachePrunedCount", 0))
            if expired_streams or expired_probes or expired_hls_jobs or pruned_cache:
                logger.info(
                    "desktop_agent_janitor_reaped streams=%s probes=%s hls_jobs=%s cache_entries=%s",
                    expired_streams,
                    expired_probes,
                    expired_hls_jobs,
                    pruned_cache,
                )
        except Exception:
            logger.exception("desktop_agent_janitor_pass_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


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


def _is_public_api_path(path: str) -> bool:
    public_paths = {
        "/api/health",
        "/api/health/live",
        "/api/openapi.json",
        "/api/docs",
        "/api/redoc",
        "/api/system/capabilities",
        "/api/system/desktop-agent-release",
        "/api/desktop-agents/pair",
        "/api/desktop-agents/refresh-token",
        "/api/desktop-agents/setup-bootstrap",
        "/api/desktop-agents/setup-complete",
        "/api/desktop-agents/manifest-sync",
        "/api/desktop-agents/diagnostic-events",
    }
    if path in public_paths:
        return True
    if path.startswith("/api/desktop-agents/stream-sessions/"):
        return True
    if path.startswith("/api/desktop-agents/hls-jobs/"):
        return True
    if path.startswith("/api/media/streams/"):
        return True
    if path.startswith("/api/projects/") and "/media/instances/" in path and path.endswith("/relay-file"):
        return True
    if path.startswith("/api/system/desktop-agent-release/assets/"):
        return True
    return path.startswith("/api/auth/")


def _extract_project_id(path: str) -> str | None:
    prefix = "/api/projects/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix) :]
    if not remainder:
        return None
    project_id = remainder.split("/", 1)[0].strip()
    return project_id or None


def create_app() -> FastAPI:
    _configure_logging()
    validate_hosted_runtime_or_raise()
    http_config = current_http_runtime_config()
    features = current_runtime_features()
    for warning in hosted_runtime_warnings():
        logger.warning("hosted_deployment_warning %s", warning)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        ready, runtime = collect_runtime_status()
        janitor_task: asyncio.Task[None] | None = None
        janitor_stop: asyncio.Event | None = None
        try:
            sql_cfg = current_sql_runtime_config()
            sql_backend = sql_cfg.backend
        except Exception:
            sql_backend = "unknown"
        logger.info(
            "startup app=%s version=%s ready=%s app_mode=%s sql_backend=%s auth_enabled=%s asr_enabled=%s public_origin=%s",
            APP_NAME,
            APP_VERSION,
            ready,
            runtime.get("appMode"),
            sql_backend,
            runtime.get("authEnabled"),
            runtime.get("asrEnabled"),
            http_config.public_origin,
        )
        janitor_interval_seconds = _desktop_agent_janitor_interval_seconds()
        if features.app_mode == "hosted" and janitor_interval_seconds > 0:
            janitor_stop = asyncio.Event()
            janitor_task = asyncio.create_task(_desktop_agent_janitor_loop(janitor_stop, janitor_interval_seconds))
            logger.info("desktop_agent_janitor_started interval_seconds=%s", janitor_interval_seconds)
        try:
            yield
        finally:
            if janitor_stop is not None:
                janitor_stop.set()
            if janitor_task is not None:
                await janitor_task

    app = FastAPI(
        title=f"{APP_NAME} API",
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        lifespan=lifespan,
    )

    if http_config.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(http_config.allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if http_config.trusted_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(http_config.trusted_hosts))

    register_exception_handlers(app)

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        request_id = str(request.headers.get("X-Request-ID", "")).strip() or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
            raise
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request request_id=%s method=%s path=%s status=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            getattr(response, "status_code", "unknown"),
            duration_ms,
        )
        return response

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if not getattr(request.state, "request_id", None):
            request.state.request_id = str(request.headers.get("X-Request-ID", "")).strip() or uuid.uuid4().hex
        request.state.auth_user = None
        features = current_runtime_features()
        path = request.url.path

        if request.method.upper() == "OPTIONS" or not path.startswith("/api"):
            return await call_next(request)
        if not features.auth_enabled or _is_public_api_path(path):
            return await call_next(request)

        auth_store = get_auth_store()
        user = resolve_session_user(request, auth_store)
        if user is None:
            return auth_error_response(
                status_code=401,
                code="UNAUTHORIZED",
                message="Authentication required",
                request_id=getattr(request.state, "request_id", None),
            )

        request.state.auth_user = user
        project_id = _extract_project_id(path)
        if project_id is not None and not auth_store.user_has_project_access(user.user_id, project_id):
            return auth_error_response(
                status_code=403,
                code="FORBIDDEN",
                message="Project access denied",
                request_id=getattr(request.state, "request_id", None),
            )

        return await call_next(request)

    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(desktop_agents.router, prefix="/api", tags=["desktop-agents"])
    app.include_router(projects.router, prefix="/api", tags=["projects"])
    app.include_router(materials.router, prefix="/api", tags=["materials"])
    app.include_router(media.router, prefix="/api", tags=["media"])
    app.include_router(learning_tasks.router, prefix="/api", tags=["learning-tasks"])
    app.include_router(review.router, prefix="/api", tags=["review"])
    app.include_router(layers.router, prefix="/api", tags=["layers"])
    app.include_router(push.router, prefix="/api", tags=["push"])
    app.include_router(validation.router, prefix="/api", tags=["validation"])
    app.include_router(asr.router, prefix="/api", tags=["asr"])
    app.include_router(system.router, prefix="/api", tags=["system"])

    @app.get("/api/health/live")
    def health_live() -> dict:
        return {"ok": True, "data": {"status": "ok", "app": APP_NAME, "version": APP_VERSION}}

    @app.get("/api/health")
    def health() -> JSONResponse:
        ready, runtime = collect_runtime_status()
        data = {
            "status": "ok" if ready else "degraded",
            "app": APP_NAME,
            "version": APP_VERSION,
            "runtimeMode": os.getenv("PLM_RUNTIME_MODE", "unknown"),
            "publicOrigin": http_config.public_origin,
            "allowedOrigins": list(http_config.allowed_origins),
            "trustedHosts": list(http_config.trusted_hosts),
            **runtime,
        }
        return JSONResponse(status_code=200 if ready else 503, content={"ok": ready, "data": data})

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
