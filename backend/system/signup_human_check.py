import hashlib
import logging
import os
import time
from dataclasses import dataclass

from altcha import Payload, create_challenge, verify_solution

from backend.models.errors import ExternalServiceError, PreconditionFailure
from backend.system.runtime_features import current_runtime_features


logger = logging.getLogger(__name__)
_ALTCHA_PROVIDER = "altcha"
_DEFAULT_CHALLENGE_URL = "/api/auth/human-check/challenge"
_DEFAULT_ALGORITHM = "SHA-256"
_DEFAULT_HMAC_ALGORITHM = "SHA-256"
_DEFAULT_COST = 1000
_DEFAULT_TTL_SECONDS = 600
_USED_TOKEN_DIGESTS: dict[str, int] = {}
_MAX_USED_TOKEN_DIGESTS = 10_000


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


@dataclass(frozen=True, slots=True)
class SignupHumanCheckConfig:
    requested: bool
    auth_enabled: bool
    provider: str
    hmac_secret: str | None
    challenge_url: str
    algorithm: str
    cost: int
    ttl_seconds: int
    hmac_algorithm: str
    ready: bool

    @property
    def enabled(self) -> bool:
        return bool(self.requested and self.auth_enabled and self.ready)


def current_signup_human_check_config() -> SignupHumanCheckConfig:
    hmac_secret = _env_text("LEARNINGPYRAMID_ALTCHA_HMAC_SECRET")
    return SignupHumanCheckConfig(
        requested=_env_bool("LEARNINGPYRAMID_ENABLE_SIGNUP_HUMAN_CHECK", False),
        auth_enabled=current_runtime_features().auth_enabled,
        provider=_ALTCHA_PROVIDER,
        hmac_secret=hmac_secret,
        challenge_url=_env_text("LEARNINGPYRAMID_ALTCHA_CHALLENGE_URL") or _DEFAULT_CHALLENGE_URL,
        algorithm=_env_text("LEARNINGPYRAMID_ALTCHA_ALGORITHM") or _DEFAULT_ALGORITHM,
        cost=_env_int("LEARNINGPYRAMID_ALTCHA_COST", _DEFAULT_COST, minimum=1),
        ttl_seconds=_env_int("LEARNINGPYRAMID_ALTCHA_CHALLENGE_TTL_SECONDS", _DEFAULT_TTL_SECONDS, minimum=30),
        hmac_algorithm=_env_text("LEARNINGPYRAMID_ALTCHA_HMAC_ALGORITHM") or _DEFAULT_HMAC_ALGORITHM,
        ready=bool(hmac_secret),
    )


def signup_human_check_enabled() -> bool:
    return current_signup_human_check_config().enabled


def build_signup_human_check_challenge() -> dict[str, object]:
    config = current_signup_human_check_config()
    if not config.enabled:
        raise PreconditionFailure("human verification is not enabled")
    try:
        challenge = create_challenge(
            algorithm=config.algorithm,
            cost=config.cost,
            expires_at=int(time.time()) + config.ttl_seconds,
            data={"purpose": "signup"},
            hmac_secret=str(config.hmac_secret),
            hmac_algorithm=config.hmac_algorithm,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.exception("failed to create signup human check challenge")
        raise ExternalServiceError("Human verification is temporarily unavailable") from exc
    return challenge.to_dict()


def _remember_verified_token(token: str, *, now_seconds: int, ttl_seconds: int) -> bool:
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    expired = [key for key, expires_at in _USED_TOKEN_DIGESTS.items() if expires_at <= now_seconds]
    for key in expired:
        _USED_TOKEN_DIGESTS.pop(key, None)
    if digest in _USED_TOKEN_DIGESTS:
        return False
    if len(_USED_TOKEN_DIGESTS) >= _MAX_USED_TOKEN_DIGESTS:
        oldest_key = min(_USED_TOKEN_DIGESTS, key=_USED_TOKEN_DIGESTS.__getitem__)
        _USED_TOKEN_DIGESTS.pop(oldest_key, None)
    _USED_TOKEN_DIGESTS[digest] = now_seconds + ttl_seconds
    return True


def verify_signup_human_check(token: str | None, *, remote_ip: str | None = None) -> None:
    config = current_signup_human_check_config()
    if not config.enabled:
        return
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise PreconditionFailure("human verification is required for registration")

    try:
        payload = Payload.from_base64(normalized_token)
        if payload.challenge.parameters.data != {"purpose": "signup"}:
            raise ValueError("ALTCHA challenge purpose mismatch")
        result = verify_solution(
            normalized_token,
            str(config.hmac_secret),
            hmac_algorithm=config.hmac_algorithm,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.exception("failed to validate signup human check")
        raise ExternalServiceError("Human verification is temporarily unavailable") from exc

    if not bool(getattr(result, "verified", False)):
        logger.info(
            "signup human check rejected: expired=%s invalid_signature=%s invalid_solution=%s error=%s",
            getattr(result, "expired", None),
            getattr(result, "invalid_signature", None),
            getattr(result, "invalid_solution", None),
            getattr(result, "error", None),
        )
        raise PreconditionFailure("human verification failed")

    if not _remember_verified_token(normalized_token, now_seconds=int(time.time()), ttl_seconds=config.ttl_seconds):
        logger.info("signup human check rejected: replayed token")
        raise PreconditionFailure("human verification failed")
