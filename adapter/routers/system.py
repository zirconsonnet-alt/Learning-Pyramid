from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from adapter.auth import require_request_auth_user
from adapter.desktop_agent_setup import collect_desktop_agent_setup_catalog
from adapter.desktop_agent_monitor import (
    collect_user_desktop_agent_monitor,
    list_user_desktop_agent_diagnostic_event_dtos,
)
from adapter.deps import get_api, get_auth_store, get_desktop_agent_runtime, get_desktop_agent_setup_manager
from adapter.runtime_status import collect_runtime_status
from adapter.schemas import CreateDesktopAgentSetupSessionRequest
from backend.system.desktop_agent_release import (
    get_desktop_agent_release_asset_dto,
    get_latest_desktop_agent_release,
    resolve_desktop_agent_release_asset,
)
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.desktop_agent_runtime import DesktopAgentRuntime
from backend.system.runtime_features import current_runtime_features
from backend.system.http_runtime_config import current_http_runtime_config


router = APIRouter()


def _build_relay_diagnostic_export_filename() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"relay-diagnostics-{stamp}.jsonl"


@router.get("/system/capabilities")
def get_system_capabilities() -> dict:
    features = current_runtime_features()
    ready, runtime = collect_runtime_status()
    return {
        "ok": True,
        "data": {
            "appMode": features.app_mode,
            "asrEnabled": features.asr_enabled,
            "serverMediaStreamEnabled": features.server_media_stream_enabled,
            "browserLocalMediaEnabled": features.browser_local_media_enabled,
            "authEnabled": features.auth_enabled,
            "allowSignup": features.allow_signup,
            "sqlBackend": runtime.get("sqlBackend"),
            "ready": ready,
        },
    }


@router.get("/system/runtime")
def get_system_runtime() -> JSONResponse:
    ready, runtime = collect_runtime_status()
    return JSONResponse(status_code=200 if ready else 503, content={"ok": ready, "data": runtime})


@router.get("/system/desktop-agent-release")
def get_desktop_agent_release(currentVersion: str | None = Query(default=None)) -> dict:
    return {
        "ok": True,
        "data": get_latest_desktop_agent_release(current_version=currentVersion),
    }


@router.get("/system/desktop-agent/setup-catalog")
def get_desktop_agent_setup_catalog_route(
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {
        "ok": True,
        "data": collect_desktop_agent_setup_catalog(user.user_id, auth_store=auth_store, api=api),
    }


@router.post("/system/desktop-agent/setup-sessions")
def create_desktop_agent_setup_session(
    request: Request,
    req: CreateDesktopAgentSetupSessionRequest,
    auth_store: AuthStore = Depends(get_auth_store),
    setup_manager=Depends(get_desktop_agent_setup_manager),
) -> dict:
    user = require_request_auth_user(request)
    preferred_project_id = None if req.preferredProjectId is None else str(req.preferredProjectId).strip() or None
    if preferred_project_id is not None and not auth_store.user_has_project_access(user.user_id, preferred_project_id):
        raise HTTPException(status_code=403, detail="Project access denied")
    http_config = current_http_runtime_config()
    server_url = str(http_config.public_origin or f"{request.base_url.scheme}://{request.base_url.netloc}").rstrip("/")
    return {
        "ok": True,
        "data": setup_manager.create_session(
            user_id=user.user_id,
            server_url=server_url,
            preferred_project_id=preferred_project_id,
        ),
    }


@router.get("/system/desktop-agent-release/assets/{filename}")
def download_desktop_agent_release_asset(filename: str) -> FileResponse:
    asset_path = resolve_desktop_agent_release_asset(filename)
    if asset_path is None:
        raise HTTPException(status_code=404, detail="Desktop agent release asset not found")
    asset = get_desktop_agent_release_asset_dto(filename)
    headers = {}
    if asset is not None:
        headers["X-Checksum-Sha256"] = str(asset.get("sha256") or "")
        headers["X-Integrity-Mode"] = str(asset.get("integrityMode") or "sha256")
        signature = asset.get("signature")
        if isinstance(signature, dict):
            headers["X-Signature-Status"] = str(signature.get("status") or "")
        silent_install = asset.get("silentInstall")
        if isinstance(silent_install, dict):
            headers["X-Silent-Install-Supported"] = "true" if bool(silent_install.get("supported")) else "false"
    return FileResponse(path=str(asset_path), filename=asset_path.name, headers=headers)


@router.get("/system/relay-monitor")
def get_relay_monitor(
    request: Request,
    diagnosticSinceHours: int = Query(default=24, ge=1, le=24 * 7),
    diagnosticLimit: int = Query(default=12, ge=1, le=200),
    alertSinceHours: int = Query(default=1, ge=1, le=24),
    diagnosticLevel: str | None = Query(default=None, max_length=32),
    diagnosticCategory: str | None = Query(default=None, max_length=64),
    diagnosticEventType: str | None = Query(default=None, max_length=64),
    diagnosticAgentId: str | None = Query(default=None, max_length=128),
    diagnosticProjectId: str | None = Query(default=None, max_length=128),
    diagnosticQuery: str | None = Query(default=None, max_length=256),
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
    api: SystemAPI = Depends(get_api),
) -> dict:
    user = require_request_auth_user(request)
    return {
        "ok": True,
        "data": collect_user_desktop_agent_monitor(
            user_id=user.user_id,
            auth_store=auth_store,
            runtime=runtime,
            api=api,
            recent_diagnostic_limit=diagnosticLimit,
            diagnostic_since_hours=diagnosticSinceHours,
            alert_since_hours=alertSinceHours,
            diagnostic_level=diagnosticLevel,
            diagnostic_category=diagnosticCategory,
            diagnostic_event_type=diagnosticEventType,
            diagnostic_agent_id=diagnosticAgentId,
            diagnostic_project_id=diagnosticProjectId,
            diagnostic_query=diagnosticQuery,
        ),
    }


@router.get("/system/relay-diagnostics/export")
def export_relay_diagnostics(
    request: Request,
    diagnosticSinceHours: int = Query(default=24, ge=1, le=24 * 30),
    diagnosticLimit: int = Query(default=500, ge=1, le=5000),
    diagnosticLevel: str | None = Query(default=None, max_length=32),
    diagnosticCategory: str | None = Query(default=None, max_length=64),
    diagnosticEventType: str | None = Query(default=None, max_length=64),
    diagnosticAgentId: str | None = Query(default=None, max_length=128),
    diagnosticProjectId: str | None = Query(default=None, max_length=128),
    diagnosticQuery: str | None = Query(default=None, max_length=256),
    auth_store: AuthStore = Depends(get_auth_store),
) -> StreamingResponse:
    user = require_request_auth_user(request)
    rows = list_user_desktop_agent_diagnostic_event_dtos(
        user_id=user.user_id,
        auth_store=auth_store,
        diagnostic_since_hours=diagnosticSinceHours,
        limit=diagnosticLimit,
        level=diagnosticLevel,
        category=diagnosticCategory,
        event_type=diagnosticEventType,
        agent_id=diagnosticAgentId,
        project_id=diagnosticProjectId,
        query=diagnosticQuery,
    )

    def iter_lines():
        for row in rows:
            yield json.dumps(row, ensure_ascii=False) + "\n"

    return StreamingResponse(
        iter_lines(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{_build_relay_diagnostic_export_filename()}"',
        },
    )
