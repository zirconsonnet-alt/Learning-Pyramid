from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from backend.models.errors import ExternalServiceError, PreconditionFailure
from backend.system.runtime_features import current_runtime_features


logger = logging.getLogger(__name__)
_TURNSTILE_SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TURNSTILE_EXPECTED_ACTION = "signup"


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


def _env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return max(minimum, int(default))
    try:
        value = int(str(raw).strip())
    except Exception:
        value = int(default)
    return max(minimum, value)


def _env_text(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


def _expected_hostname() -> str | None:
    explicit = _env_text("PLM_TURNSTILE_EXPECTED_HOSTNAME")
    if explicit:
        return explicit
    public_origin = _env_text("PLM_PUBLIC_ORIGIN")
    if not public_origin:
        return None
    try:
        parsed = urlsplit(public_origin)
    except Exception:
        return None
    return str(parsed.hostname or "").strip() or None


@dataclass(frozen=True, slots=True)
class SignupHumanCheckConfig:
    requested: bool
    auth_enabled: bool
    site_key: str | None
    secret_key: str | None
    expected_hostname: str | None
    timeout_seconds: int
    ready: bool

    @property
    def enabled(self) -> bool:
        return bool(self.requested and self.auth_enabled and self.ready)


def current_signup_human_check_config() -> SignupHumanCheckConfig:
    site_key = _env_text("PLM_TURNSTILE_SITE_KEY")
    secret_key = _env_text("PLM_TURNSTILE_SECRET_KEY")
    return SignupHumanCheckConfig(
        requested=_env_bool("PLM_ENABLE_SIGNUP_HUMAN_CHECK", False),
        auth_enabled=current_runtime_features().auth_enabled,
        site_key=site_key,
        secret_key=secret_key,
        expected_hostname=_expected_hostname(),
        timeout_seconds=_env_int("PLM_TURNSTILE_TIMEOUT_SECONDS", 5, minimum=1),
        ready=bool(site_key and secret_key),
    )


def signup_human_check_enabled() -> bool:
    return current_signup_human_check_config().enabled


def verify_signup_human_check(token: str | None, *, remote_ip: str | None = None) -> None:
    config = current_signup_human_check_config()
    if not config.enabled:
        return
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise PreconditionFailure("human verification is required for registration")

    payload = {
        "secret": str(config.secret_key),
        "response": normalized_token,
        "idempotency_key": str(uuid.uuid4()),
    }
    if remote_ip:
        payload["remoteip"] = str(remote_ip).strip()

    request = urllib.request.Request(
        _TURNSTILE_SITEVERIFY_URL,
        data=urllib.parse.urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            raw_payload = response.read().decode("utf-8")
        result = json.loads(raw_payload)
    except Exception as exc:
        logger.exception("failed to validate signup human check")
        raise ExternalServiceError("Human verification is temporarily unavailable") from exc

    if not isinstance(result, dict) or not bool(result.get("success", False)):
        logger.info("signup human check rejected: %s", result.get("error-codes") if isinstance(result, dict) else None)
        raise PreconditionFailure("human verification failed")

    if config.expected_hostname and str(result.get("hostname") or "").strip() != config.expected_hostname:
        logger.warning(
            "signup human check hostname mismatch: expected=%s actual=%s",
            config.expected_hostname,
            result.get("hostname"),
        )
        raise PreconditionFailure("human verification failed")

    if str(result.get("action") or "").strip() != _TURNSTILE_EXPECTED_ACTION:
        logger.warning("signup human check action mismatch: %s", result.get("action"))
        raise PreconditionFailure("human verification failed")
