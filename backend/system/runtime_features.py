from __future__ import annotations

import os
from dataclasses import dataclass

from backend.models.enums import ClientRuntimeKind, RuntimeCapability
from backend.models.errors import PreconditionFailure
from backend.models.project_config import LocalModelConfig, LocalServiceConfig, NativeRuntimeConfig
from backend.system.local_whisper import BUILTIN_WHISPER_BASE_URL


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


def _env_text(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


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


def default_client_runtime_kind() -> ClientRuntimeKind:
    raw = (os.getenv("PLM_CLIENT_RUNTIME_KIND") or "").strip().upper()
    if raw:
        try:
            return ClientRuntimeKind(raw)
        except ValueError:
            pass
    return ClientRuntimeKind.DESKTOP_WEB if current_runtime_features().app_mode == "hosted" else ClientRuntimeKind.DESKTOP_NATIVE


def default_runtime_capabilities(runtime_kind: ClientRuntimeKind | None = None) -> frozenset[RuntimeCapability]:
    kind = runtime_kind or default_client_runtime_kind()
    if kind == ClientRuntimeKind.DESKTOP_NATIVE:
        caps = {
            RuntimeCapability.VIDEO_PLAYBACK,
            RuntimeCapability.LIGHT_REVIEW,
            RuntimeCapability.NATIVE_FS_BINDING,
            RuntimeCapability.MEMORY_CANVAS_EDIT,
            RuntimeCapability.STORY_GENERATION,
        }
        if current_runtime_features().asr_enabled:
            caps.add(RuntimeCapability.LOCAL_ASR)
        # Native local LLM / recommender default to enabled in local mode; specific model
        # availability is checked separately when an API is invoked.
        caps.add(RuntimeCapability.LOCAL_LLM_QA)
        caps.add(RuntimeCapability.LOCAL_RECOMMENDER)
        return frozenset(caps)
    return frozenset({RuntimeCapability.VIDEO_PLAYBACK, RuntimeCapability.LIGHT_REVIEW})


def _service_config_from_env(
    *,
    prefix: str,
    default_base_url: str | None = None,
) -> LocalServiceConfig | None:
    base_url = _env_text(f"PLM_NATIVE_{prefix}_BASE_URL") or default_base_url
    if base_url is None:
        return None
    cfg = LocalServiceConfig(
        base_url=base_url,
        api_key=_env_text(f"PLM_NATIVE_{prefix}_API_KEY"),
        model_name=_env_text(f"PLM_NATIVE_{prefix}_MODEL"),
    )
    cfg.validate_write_time()
    return cfg


def current_native_runtime_config(
    runtime_kind: ClientRuntimeKind | None = None,
    runtime_capabilities: frozenset[RuntimeCapability] | None = None,
) -> NativeRuntimeConfig:
    kind = runtime_kind or default_client_runtime_kind()
    caps = runtime_capabilities or default_runtime_capabilities(kind)

    asr_cfg: LocalServiceConfig | None = None
    if kind == ClientRuntimeKind.DESKTOP_NATIVE and RuntimeCapability.LOCAL_ASR in caps and current_runtime_features().asr_enabled:
        asr_cfg = _service_config_from_env(prefix="ASR", default_base_url=BUILTIN_WHISPER_BASE_URL)

    recommender_cfg: LocalServiceConfig | None = None
    if kind == ClientRuntimeKind.DESKTOP_NATIVE and RuntimeCapability.LOCAL_RECOMMENDER in caps:
        recommender_cfg = _service_config_from_env(prefix="RECOMMENDER")

    llm_cfg: LocalServiceConfig | None = None
    if kind == ClientRuntimeKind.DESKTOP_NATIVE and RuntimeCapability.LOCAL_LLM_QA in caps:
        llm_cfg = _service_config_from_env(prefix="LLM_QA")

    story_cfg: LocalServiceConfig | None = None
    if kind == ClientRuntimeKind.DESKTOP_NATIVE and RuntimeCapability.STORY_GENERATION in caps:
        story_cfg = _service_config_from_env(prefix="STORY_GENERATOR")

    config = NativeRuntimeConfig(
        runtime_kind=kind,
        capabilities=caps,
        local_models=LocalModelConfig(
            asr=asr_cfg,
            llm_qa=llm_cfg,
            recommender=recommender_cfg,
            story_generator=story_cfg,
        ),
    )
    config.validate_runtime()
    return config


def require_asr_enabled() -> None:
    if current_runtime_features().asr_enabled:
        return
    raise PreconditionFailure("ASR is disabled in this deployment")


def require_server_media_stream_enabled() -> None:
    if current_runtime_features().server_media_stream_enabled:
        return
    raise PreconditionFailure("Server-side media streaming is disabled in this deployment")
