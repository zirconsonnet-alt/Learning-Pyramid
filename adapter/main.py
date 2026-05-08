from __future__ import annotations

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.trustedhost import TrustedHostMiddleware

from adapter.auth import auth_error_response, resolve_session_user
from adapter.errors import register_exception_handlers
from adapter.deps import get_api, get_auth_store
from adapter.runtime_status import collect_runtime_status
from adapter.routers import admin, asr, auth, friends, layers, learning_tasks, materials, media, membership, profile, projects, push, review, system, validation
from backend.system.hosted_deployment_checks import hosted_runtime_warnings, validate_hosted_runtime_or_raise
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.runtime_features import current_runtime_features
from backend.system.sql_backend import current_sql_runtime_config
from backend.system.public_downloads import resolve_public_download_asset
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
        "/api/system/public-downloads",
        "/api/guide/demo-media/study-review",
    }
    if path in public_paths:
        return True
    if path == "/api/payments/wechat/notify":
        return True
    if path == "/api/payments/wechat/refund-notify":
        return True
    if path == "/api/payments/wechat/transfer-notify":
        return True
    if path == "/api/commissions/payout-identity/wechat/mobile-bind":
        return True
    if path == "/api/commissions/payout-identity/wechat/bind":
        return True
    if path.startswith("/api/commissions/withdrawals/") and path.endswith("/wechat-confirmation"):
        return True
    if path.startswith("/api/public/asr-bridge/"):
        return True
    return path.startswith("/api/auth/")


def _public_api_path_supports_optional_auth(path: str) -> bool:
    return path in {
        "/api/system/capabilities",
        "/api/commissions/payout-identity/wechat/bind",
    }


def _extract_project_id(path: str) -> str | None:
    prefix = "/api/projects/"
    if not path.startswith(prefix):
        return None
    remainder = path[len(prefix) :]
    if not remainder:
        return None
    project_id = remainder.split("/", 1)[0].strip()
    return project_id or None


def _project_precondition_error_response(request: Request, message: str) -> JSONResponse:
    payload = {"ok": False, "error": {"code": "PRECONDITION", "message": message}}
    request_id = getattr(request.state, "request_id", None)
    headers = {"X-Request-ID": str(request_id)} if request_id else None
    return JSONResponse(status_code=400, content=payload, headers=headers)


def _grant_subject_material_project_access_if_allowed(api, auth_store, user_id: str, project_id: str) -> bool:
    allowed = set(auth_store.list_project_ids_for_user(user_id))
    if project_id in allowed:
        return True
    try:
        payload = api.get_subject_context(project_id)
    except Exception:
        return False

    subject_id = str(getattr(payload["subject"], "project_id"))
    if subject_id not in allowed:
        return False
    for material in payload["materials"]:
        material_project_id = getattr(material, "project_id", None)
        if material_project_id is not None:
            auth_store.add_project_owner(str(material_project_id), user_id)
    auth_store.add_project_owner(project_id, user_id)
    return True


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
        try:
            yield
        finally:
            return

    app = FastAPI(
        title=f"{APP_NAME} API",
        openapi_url="/api/openapi.json" if http_config.api_docs_enabled else None,
        docs_url="/api/docs" if http_config.api_docs_enabled else None,
        redoc_url="/api/redoc" if http_config.api_docs_enabled else None,
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
        project_id = _extract_project_id(path)
        if project_id is not None:
            api = get_api()
            try:
                await run_in_threadpool(api.require_material_project, project_id)
            except Exception as exc:
                if exc.__class__.__name__ == "PreconditionFailure":
                    return _project_precondition_error_response(request, str(exc))
                raise

        if not features.auth_enabled:
            return await call_next(request)

        if _is_public_api_path(path):
            if _public_api_path_supports_optional_auth(path):
                auth_store = get_auth_store()
                request.state.auth_user = await run_in_threadpool(resolve_session_user, request, auth_store)
            return await call_next(request)

        auth_store = get_auth_store()
        user = await run_in_threadpool(resolve_session_user, request, auth_store)
        if user is None:
            return auth_error_response(
                status_code=401,
                code="UNAUTHORIZED",
                message="Authentication required",
                request_id=getattr(request.state, "request_id", None),
            )

        request.state.auth_user = user
        has_project_access = True
        if project_id is not None:
            api = get_api()
            has_project_access = await run_in_threadpool(
                _grant_subject_material_project_access_if_allowed,
                api,
                auth_store,
                user.user_id,
                project_id,
            )
        if project_id is not None and not has_project_access:
            return auth_error_response(
                status_code=403,
                code="FORBIDDEN",
                message="Project access denied",
                request_id=getattr(request.state, "request_id", None),
            )

        return await call_next(request)

    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(profile.router, prefix="/api", tags=["profile"])
    app.include_router(membership.router, prefix="/api", tags=["membership"])
    app.include_router(friends.router, prefix="/api", tags=["friends"])
    app.include_router(admin.router, prefix="/api", tags=["admin"])
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

    @app.get("/downloads/{full_path:path}", include_in_schema=False)
    def serve_public_download(full_path: str):
        asset = resolve_public_download_asset(full_path)
        if asset is None:
            return PlainTextResponse("Not found", status_code=404)
        return FileResponse(str(asset), filename=asset.name)

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
