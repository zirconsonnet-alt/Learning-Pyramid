import os
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from backend.system.runtime_features import current_runtime_features


def _split_csv(value: str | None) -> tuple[str, ...]:
    if value is None:
        return tuple()
    items = []
    for raw in str(value).split(","):
        item = raw.strip()
        if item:
            items.append(item)
    return tuple(items)


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


def _default_dev_origins() -> tuple[str, ...]:
    return ("http://localhost:5173", "http://localhost:3000")


def _normalized_origin(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _dedupe(items: Iterable[str]) -> tuple[str, ...]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class HttpRuntimeConfig:
    allowed_origins: tuple[str, ...]
    trusted_hosts: tuple[str, ...]
    public_origin: str | None
    proxy_headers_enabled: bool
    forwarded_allow_ips: str
    api_docs_enabled: bool


def current_http_runtime_config() -> HttpRuntimeConfig:
    features = current_runtime_features()
    public_origin = _normalized_origin(os.getenv("LEARNINGPYRAMID_PUBLIC_ORIGIN"))

    raw_allowed_origins = _split_csv(os.getenv("LEARNINGPYRAMID_ALLOWED_ORIGINS"))
    if raw_allowed_origins:
        allowed_origins = raw_allowed_origins
    elif features.app_mode == "local":
        allowed_origins = _default_dev_origins()
    elif public_origin is not None:
        allowed_origins = (public_origin,)
    else:
        allowed_origins = tuple()

    raw_trusted_hosts = _split_csv(os.getenv("LEARNINGPYRAMID_TRUSTED_HOSTS"))
    if raw_trusted_hosts:
        trusted_hosts = raw_trusted_hosts
    elif public_origin is not None:
        parsed = urlparse(public_origin)
        trusted_hosts = (parsed.hostname,) if parsed.hostname else tuple()
    else:
        trusted_hosts = tuple()

    proxy_headers_enabled = str(os.getenv("LEARNINGPYRAMID_PROXY_HEADERS", "true")).strip().lower() in {"1", "true", "yes", "on"}
    forwarded_allow_ips = (os.getenv("LEARNINGPYRAMID_FORWARDED_ALLOW_IPS") or "127.0.0.1").strip() or "127.0.0.1"
    api_docs_enabled = _env_bool("LEARNINGPYRAMID_ENABLE_API_DOCS", features.app_mode == "local")

    return HttpRuntimeConfig(
        allowed_origins=_dedupe(allowed_origins),
        trusted_hosts=trusted_hosts,
        public_origin=public_origin,
        proxy_headers_enabled=proxy_headers_enabled,
        forwarded_allow_ips=forwarded_allow_ips,
        api_docs_enabled=api_docs_enabled,
    )
