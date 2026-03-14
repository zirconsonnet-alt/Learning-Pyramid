from __future__ import annotations

import os
from dataclasses import dataclass

from backend.models.errors import PreconditionFailure


@dataclass(frozen=True, slots=True)
class RuntimeFeatures:
    app_mode: str
    asr_enabled: bool
    server_media_stream_enabled: bool
    browser_local_media_enabled: bool
    auth_enabled: bool
    allow_signup: bool


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return bool(default)
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return bool(default)


def current_runtime_features() -> RuntimeFeatures:
    raw_mode = (os.getenv("PLM_APP_MODE") or os.getenv("APP_MODE") or "local").strip().lower()
    app_mode = "hosted" if raw_mode == "hosted" else "local"
    hosted = app_mode == "hosted"
    return RuntimeFeatures(
        app_mode=app_mode,
        asr_enabled=_env_bool("PLM_ENABLE_ASR", not hosted),
        server_media_stream_enabled=_env_bool("PLM_ENABLE_SERVER_MEDIA_STREAM", not hosted),
        browser_local_media_enabled=_env_bool("PLM_ENABLE_BROWSER_LOCAL_MEDIA", True),
        auth_enabled=_env_bool("PLM_ENABLE_AUTH", hosted),
        allow_signup=_env_bool("PLM_ALLOW_SIGNUP", True),
    )


def require_asr_enabled() -> None:
    if current_runtime_features().asr_enabled:
        return
    raise PreconditionFailure("ASR is disabled in this deployment")


def require_server_media_stream_enabled() -> None:
    if current_runtime_features().server_media_stream_enabled:
        return
    raise PreconditionFailure("Server-side media streaming is disabled in this deployment")
