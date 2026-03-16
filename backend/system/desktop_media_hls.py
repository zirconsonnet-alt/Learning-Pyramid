from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from backend.models.hls_cache_entry import HlsCacheEntry
from backend.models.errors import PreconditionFailure
from backend.system.app_paths import desktop_media_cache_dir

DEFAULT_HLS_HEIGHT_MAX = 720
DEFAULT_HLS_VIDEO_BITRATE = "1200k"
DEFAULT_HLS_AUDIO_BITRATE = "96k"
DEFAULT_HLS_SEGMENT_SECONDS = 3


def _env_positive_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return int(default) if value <= 0 else value


def current_hls_profile() -> dict[str, int | str]:
    return {
        "heightMax": _env_positive_int("PLM_AGENT_HLS_HEIGHT_MAX", DEFAULT_HLS_HEIGHT_MAX),
        "videoBitrate": str(os.getenv("PLM_AGENT_HLS_VIDEO_BITRATE") or DEFAULT_HLS_VIDEO_BITRATE).strip()
        or DEFAULT_HLS_VIDEO_BITRATE,
        "audioBitrate": str(os.getenv("PLM_AGENT_HLS_AUDIO_BITRATE") or DEFAULT_HLS_AUDIO_BITRATE).strip()
        or DEFAULT_HLS_AUDIO_BITRATE,
        "segmentSeconds": _env_positive_int("PLM_AGENT_HLS_SEGMENT_SECONDS", DEFAULT_HLS_SEGMENT_SECONDS),
    }


def hls_cache_ttl_seconds() -> int:
    return _env_positive_int("PLM_AGENT_CACHE_TTL_SECONDS", 86_400)


def hls_cache_max_bytes() -> int:
    return _env_positive_int("PLM_AGENT_CACHE_MAX_BYTES", 21_474_836_480)


def serialize_hls_profile(profile: dict[str, int | str]) -> str:
    return json.dumps(dict(profile), sort_keys=True, separators=(",", ":"))


def build_hls_cache_key(
    *,
    project_id: str,
    instance_id: str,
    agent_id: str,
    profile: dict[str, int | str],
) -> str:
    material = "|".join((str(project_id), str(instance_id), str(agent_id), serialize_hls_profile(profile)))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def normalize_hls_artifact_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip().strip("/")
    if not raw:
        raise PreconditionFailure("HLS artifact path must be non-empty")
    path = PurePosixPath(raw)
    if path.is_absolute():
        raise PreconditionFailure("HLS artifact path must be relative")
    first = path.parts[0] if path.parts else ""
    if ":" in first:
        raise PreconditionFailure("HLS artifact path must not include a drive prefix")
    normalized_parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            raise PreconditionFailure("HLS artifact path must not contain '..'")
        normalized_parts.append(part)
    if not normalized_parts:
        raise PreconditionFailure("HLS artifact path must be non-empty")
    return "/".join(normalized_parts)


def hls_cache_root() -> Path:
    root = desktop_media_cache_dir().expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_hls_artifact_disk_path(cache_key: str, artifact_path: str) -> Path:
    normalized_artifact_path = normalize_hls_artifact_path(artifact_path)
    base = (hls_cache_root() / str(cache_key)).resolve()
    target = (base / Path(normalized_artifact_path)).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise PreconditionFailure("HLS artifact path escapes cache root") from exc
    return target


def hls_artifact_media_type(artifact_path: str) -> str:
    normalized = normalize_hls_artifact_path(artifact_path)
    lower = normalized.lower()
    if lower.endswith(".m3u8"):
        return "application/vnd.apple.mpegurl"
    if lower.endswith(".ts"):
        return "video/mp2t"
    guessed, _ = mimetypes.guess_type(normalized)
    return guessed or "application/octet-stream"


def _coerce_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _remove_cache_artifact_file(file_path: str | Path) -> None:
    root = hls_cache_root().resolve()
    target = Path(file_path).expanduser().resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return
    if target.exists() and target.is_file():
        target.unlink()
    current = target.parent
    while current != root:
        try:
            current.rmdir()
        except OSError:
            break
        current = current.parent


def prune_hls_cache(auth_store: Any, *, now: datetime | None = None) -> tuple[HlsCacheEntry, ...]:
    entries = list(auth_store.list_all_hls_cache_entries())
    if not entries:
        return ()

    cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    removed: list[HlsCacheEntry] = []
    removed_keys: set[tuple[str, str]] = set()

    def _remove_entry(entry: HlsCacheEntry) -> None:
        key = (entry.cache_key, entry.segment_name)
        if key in removed_keys:
            return
        removed_keys.add(key)
        auth_store.delete_hls_cache_entry(entry.cache_key, entry.segment_name)
        _remove_cache_artifact_file(entry.file_path)
        removed.append(entry)

    survivors: list[HlsCacheEntry] = []
    for entry in entries:
        if _coerce_utc_datetime(entry.expires_at) <= cutoff:
            _remove_entry(entry)
            continue
        survivors.append(entry)

    total_size = sum(int(entry.size_bytes) for entry in survivors)
    if total_size <= hls_cache_max_bytes():
        return tuple(removed)

    eviction_order = sorted(
        survivors,
        key=lambda item: (
            _coerce_utc_datetime(item.last_accessed_at),
            _coerce_utc_datetime(item.created_at),
            str(item.cache_key),
            str(item.segment_name),
        ),
    )
    for entry in eviction_order:
        if total_size <= hls_cache_max_bytes():
            break
        _remove_entry(entry)
        total_size -= int(entry.size_bytes)
    return tuple(removed)


def invalidate_hls_cache_entries_for_instance(
    auth_store: Any,
    *,
    project_id: str,
    instance_id: str,
    agent_id: str,
) -> tuple[HlsCacheEntry, ...]:
    removed: list[HlsCacheEntry] = []
    for entry in auth_store.list_all_hls_cache_entries():
        if (
            str(entry.project_id) != str(project_id)
            or str(entry.instance_id) != str(instance_id)
            or str(entry.agent_id) != str(agent_id)
        ):
            continue
        auth_store.delete_hls_cache_entry(entry.cache_key, entry.segment_name)
        _remove_cache_artifact_file(entry.file_path)
        removed.append(entry)
    return tuple(removed)
