from __future__ import annotations

import os
from urllib.parse import urlsplit

from backend.system.runtime_features import current_runtime_features
from backend.system.sql_backend import current_sql_runtime_config


_TRUE_VALUES = {"1", "true", "yes", "on"}
_PLACEHOLDER_MARKERS = ("change-me", "replace-me")


def _env_text(name: str) -> str:
    return str(os.getenv(name) or "").strip()


def _looks_like_placeholder(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def _postgres_password_candidate() -> str:
    direct_value = _env_text("PLM_POSTGRES_PASSWORD")
    if direct_value:
        return direct_value
    dsn = _env_text("PLM_POSTGRES_DSN")
    if not dsn:
        return ""
    try:
        parsed = urlsplit(dsn)
    except Exception:
        return ""
    return str(parsed.password or "").strip()


def hosted_runtime_blockers() -> tuple[str, ...]:
    features = current_runtime_features()
    if features.app_mode != "hosted":
        return tuple()

    blockers: list[str] = []
    if _looks_like_placeholder(_env_text("PLM_MEDIA_ACCESS_TOKEN_SECRET")):
        blockers.append("PLM_MEDIA_ACCESS_TOKEN_SECRET must be set to a non-placeholder secret in hosted mode.")
    return tuple(blockers)


def hosted_runtime_warnings() -> tuple[str, ...]:
    features = current_runtime_features()
    if features.app_mode != "hosted":
        return tuple()

    warnings: list[str] = []

    if features.allow_signup:
        warnings.append("PLM_ALLOW_SIGNUP=true leaves the hosted deployment open for self-registration.")
    if _env_text("PLM_SECURE_COOKIES").lower() not in _TRUE_VALUES:
        warnings.append("PLM_SECURE_COOKIES is disabled. Use this only for temporary plain-HTTP localhost testing.")
    if not _env_text("PLM_PUBLIC_ORIGIN"):
        warnings.append("PLM_PUBLIC_ORIGIN is empty. Set it to the external HTTPS origin before public deployment.")
    if not _env_text("PLM_TRUSTED_HOSTS"):
        warnings.append("PLM_TRUSTED_HOSTS is empty. Set it to the externally reachable host list.")

    try:
        sql_backend = current_sql_runtime_config().backend
    except Exception:
        sql_backend = None
    if sql_backend == "postgres":
        pg_password = _postgres_password_candidate()
        if not pg_password or pg_password.strip().lower() == "learningpyramid" or _looks_like_placeholder(pg_password):
            warnings.append("PostgreSQL credentials still look like example values. Update PLM_POSTGRES_PASSWORD and PLM_POSTGRES_DSN before deployment.")

    return tuple(warnings)


def validate_hosted_runtime_or_raise() -> None:
    blockers = hosted_runtime_blockers()
    if not blockers:
        return
    raise RuntimeError(" ".join(blockers))
