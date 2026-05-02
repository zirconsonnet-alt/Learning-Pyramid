from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

from backend.system.auth_rate_limit_store import current_auth_rate_limit_config
from backend.system.email_verification_delivery import current_email_verification_delivery_config
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.membership_payment_service import current_wechat_native_payment_config
from backend.system.membership_payment_service import manual_test_payment_enabled
from backend.system.password_reset_delivery import current_password_reset_delivery_config
from backend.system.runtime_features import current_runtime_features
from backend.system.signup_human_check import current_signup_human_check_config
from backend.system.sql_backend import current_sql_runtime_config
from backend.system.data_safety import validate_protected_filesystem_roots


_TRUE_VALUES = {"1", "true", "yes", "on"}
_PLACEHOLDER_MARKERS = ("change-me", "replace-me")


def _env_text(name: str) -> str:
    return str(os.getenv(name) or "").strip()


def _env_list(name: str) -> tuple[str, ...]:
    raw = _env_text(name)
    if not raw:
        return tuple()
    return tuple(item.strip() for item in raw.replace(";", ",").split(",") if item.strip())


def _wechat_app_id() -> str:
    return _env_text("PLM_WECHAT_PAY_APP_ID") or _env_text("appid") or _env_text("APPID")


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
    if features.data_safety_storage_checks_enabled:
        roots = _env_list("PLM_PROTECTED_DATA_ROOTS") or ("/data", "/app/data")
        blockers.extend(protected_storage_blockers(roots, data_expected=_env_text("PLM_PROTECTED_DATA_EXPECTED").lower() in _TRUE_VALUES))
    return tuple(blockers)


def protected_storage_blockers(roots: tuple[str | Path, ...], *, data_expected: bool) -> tuple[str, ...]:
    blockers: list[str] = []
    for finding in validate_protected_filesystem_roots(roots):
        blockers.append(f"{finding.code}: {finding.message}")
    for root in roots:
        path = Path(root)
        if not data_expected or not path.exists() or not path.is_dir():
            continue
        try:
            is_empty = not any(path.iterdir())
        except OSError:
            continue
        if is_empty:
            blockers.append(f"PROTECTED_PATH_EMPTY_UNEXPECTED: Protected data path is empty but data is expected: {path}")
    return tuple(blockers)


def hosted_runtime_warnings() -> tuple[str, ...]:
    features = current_runtime_features()
    if features.app_mode != "hosted":
        return tuple()

    warnings: list[str] = []

    public_signup = bool(features.allow_signup and not features.signup_invite_required)
    if features.allow_signup:
        warnings.append(
            "PLM_ALLOW_SIGNUP=true enables hosted self-registration endpoints. Keep it disabled unless you intentionally want bootstrap, invite-based, or public registration."
        )
    password_reset_cfg = current_password_reset_delivery_config()
    email_verification_cfg = current_email_verification_delivery_config()
    signup_human_check_cfg = current_signup_human_check_config()
    if features.allow_signup and not password_reset_cfg.enabled:
        warnings.append(
            "Public sign-up should enable password recovery. Configure PLM_ENABLE_PASSWORD_RESET=true together with PLM_SMTP_* and PLM_PUBLIC_ORIGIN before opening registration."
        )
    if public_signup and not email_verification_cfg.enabled:
        warnings.append(
            "Public sign-up without invite codes should enable email verification. Configure PLM_ENABLE_EMAIL_VERIFICATION=true together with PLM_SMTP_* and PLM_PUBLIC_ORIGIN before opening free registration."
        )
    if public_signup and not signup_human_check_cfg.enabled:
        warnings.append(
            "Public sign-up without invite codes should enable human verification. Configure PLM_ENABLE_SIGNUP_HUMAN_CHECK=true together with PLM_TURNSTILE_SITE_KEY and PLM_TURNSTILE_SECRET_KEY before opening free registration."
        )
    if password_reset_cfg.requested and not password_reset_cfg.delivery_ready:
        warnings.append(
            "Password reset email is only partially configured. Complete PLM_SMTP_HOST, PLM_SMTP_FROM_EMAIL, PLM_PUBLIC_ORIGIN, and matching SMTP credentials or disable PLM_ENABLE_PASSWORD_RESET."
        )
    if email_verification_cfg.requested and not email_verification_cfg.delivery_ready:
        warnings.append(
            "Email verification is only partially configured. Complete PLM_SMTP_HOST, PLM_SMTP_FROM_EMAIL, PLM_PUBLIC_ORIGIN, and matching SMTP credentials or disable PLM_ENABLE_EMAIL_VERIFICATION."
        )
    if signup_human_check_cfg.requested and not signup_human_check_cfg.ready:
        warnings.append(
            "Sign-up human verification is only partially configured. Complete PLM_TURNSTILE_SITE_KEY and PLM_TURNSTILE_SECRET_KEY or disable PLM_ENABLE_SIGNUP_HUMAN_CHECK."
        )
    if features.auth_enabled and not current_auth_rate_limit_config().enabled:
        warnings.append("PLM_ENABLE_AUTH_RATE_LIMITS=false disables login and sign-up throttling in hosted mode.")
    if manual_test_payment_enabled():
        warnings.append("PLM_ENABLE_MANUAL_TEST_PAYMENT=true exposes the manual_test membership payment provider in hosted mode.")
    if _env_text("PLM_SECURE_COOKIES").lower() not in _TRUE_VALUES:
        warnings.append("PLM_SECURE_COOKIES is disabled. Use this only for temporary plain-HTTP localhost testing.")
    if not _env_text("PLM_PUBLIC_ORIGIN"):
        warnings.append("PLM_PUBLIC_ORIGIN is empty. Set it to the external HTTPS origin before public deployment.")
    if not _env_text("PLM_TRUSTED_HOSTS"):
        warnings.append("PLM_TRUSTED_HOSTS is empty. Set it to the externally reachable host list.")
    if current_http_runtime_config().api_docs_enabled:
        warnings.append("PLM_ENABLE_API_DOCS=true leaves Swagger/OpenAPI endpoints enabled in hosted mode.")

    try:
        sql_backend = current_sql_runtime_config().backend
    except Exception:
        sql_backend = None
    if sql_backend == "postgres":
        pg_password = _postgres_password_candidate()
        if not pg_password or pg_password.strip().lower() == "learningpyramid" or _looks_like_placeholder(pg_password):
            warnings.append("PostgreSQL credentials still look like example values. Update PLM_POSTGRES_PASSWORD and PLM_POSTGRES_DSN before deployment.")

    wechat_config = current_wechat_native_payment_config()
    wechat_fields = (
        _wechat_app_id(),
        _env_text("PLM_WECHAT_PAY_MCH_ID"),
        _env_text("PLM_WECHAT_PAY_CERT_SERIAL_NO"),
        _env_text("PLM_WECHAT_PAY_API_V3_KEY"),
        _env_text("PLM_WECHAT_PAY_PRIVATE_KEY_PEM_PATH"),
        _env_text("PLM_WECHAT_PAY_PUBLIC_KEY_ID"),
        _env_text("PLM_WECHAT_PAY_PUBLIC_KEY_PEM_PATH"),
        _env_text("PLM_WECHAT_PAY_NOTIFY_URL"),
        _env_text("PLM_WECHAT_PAY_REFUND_NOTIFY_URL"),
    )
    if any(wechat_fields) and not wechat_config.enabled:
        warnings.append("WeChat Native payment configuration is only partially filled. Complete every required PLM_WECHAT_PAY_* value or clear them all.")
    if wechat_config.enabled and not (_env_text("PLM_PUBLIC_ORIGIN") or wechat_config.notify_url):
        warnings.append("WeChat Native payment is enabled but neither PLM_PUBLIC_ORIGIN nor PLM_WECHAT_PAY_NOTIFY_URL is configured.")
    if wechat_config.enabled and not (_env_text("PLM_PUBLIC_ORIGIN") or wechat_config.refund_notify_url or wechat_config.notify_url):
        warnings.append("WeChat Native refunds need PLM_PUBLIC_ORIGIN, PLM_WECHAT_PAY_REFUND_NOTIFY_URL, or a usable PLM_WECHAT_PAY_NOTIFY_URL before production use.")

    return tuple(warnings)


def validate_hosted_runtime_or_raise() -> None:
    blockers = hosted_runtime_blockers()
    if not blockers:
        return
    raise RuntimeError(" ".join(blockers))
