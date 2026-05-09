from typing import Any

from adapter.deps import get_api, get_auth_store
from backend.system.auth_store import AuthStore
from backend.system.email_verification_delivery import email_verification_enabled
from backend.system.runtime_features import current_runtime_features
from backend.system.signup_human_check import current_signup_human_check_config, signup_human_check_enabled
from backend.system.sql_backend import current_sql_runtime_config


def collect_runtime_status(*, user_id: str | None = None, auth_store: AuthStore | None = None) -> tuple[bool, dict[str, Any]]:
    features = current_runtime_features()
    human_check_cfg = current_signup_human_check_config()
    human_check_enabled = signup_human_check_enabled()
    payload: dict[str, Any] = {
        "appMode": features.app_mode,
        "asrEnabled": features.asr_enabled,
        "serverMediaStreamEnabled": features.server_media_stream_enabled,
        "browserLocalMediaEnabled": features.browser_local_media_enabled,
        "baiduNetdiskEnabled": features.baidu_netdisk_enabled,
        "authEnabled": features.auth_enabled,
        "allowSignup": features.allow_signup,
        "signupInviteRequired": features.signup_invite_required,
        "emailVerificationEnabled": email_verification_enabled(),
        "signupHumanCheckEnabled": human_check_enabled,
        "signupHumanCheckProvider": human_check_cfg.provider if human_check_enabled else None,
    }

    try:
        cfg = current_sql_runtime_config()
        payload["sqlBackend"] = cfg.backend
    except Exception as exc:
        payload["sqlBackend"] = "unknown"
        payload["store"] = {"ok": False, "error": str(exc)}
        payload["auth"] = {"ok": False, "error": str(exc)}
        return False, payload

    store_ready = False
    try:
        api = get_api()
        store = getattr(api.sys, "_persist_store", None)
        if store is None or not hasattr(store, "healthcheck"):
            payload["store"] = {"ok": False, "error": "Persistence store is not initialized"}
        else:
            payload["store"] = store.healthcheck()
            store_ready = bool(payload["store"].get("ok", False))
        llm_status = api.get_user_llm_status(auth_store=auth_store, user_id=user_id)
        payload["llmConfigured"] = bool(llm_status.get("llmConfigured", False))
        payload["storyGenerationConfigured"] = bool(llm_status.get("storyGenerationConfigured", False))
        payload["llmSource"] = str(llm_status.get("llmSource", "none"))
    except Exception as exc:
        payload["store"] = {"ok": False, "error": str(exc)}
        payload["llmConfigured"] = False
        payload["storyGenerationConfigured"] = False
        payload["llmSource"] = "none"

    auth_ready = True
    try:
        auth_store = get_auth_store()
        payload["auth"] = auth_store.healthcheck()
        auth_ready = bool(payload["auth"].get("ok", False))
    except Exception as exc:
        payload["auth"] = {"ok": False, "error": str(exc)}
        auth_ready = False

    ready = bool(store_ready and (auth_ready or not features.auth_enabled))
    payload["status"] = "ok" if ready else "degraded"
    return ready, payload
