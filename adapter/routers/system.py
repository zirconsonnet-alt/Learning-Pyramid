from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from adapter.runtime_status import collect_runtime_status
from backend.system.runtime_features import current_runtime_features


router = APIRouter()


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
