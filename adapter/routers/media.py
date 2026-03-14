from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path, PurePath
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from adapter.auth import get_request_auth_user, resolve_session_user
from adapter.desktop_agent_diagnostic_events import record_desktop_agent_diagnostic_event
from adapter.desktop_agent_hls_job_audit import persist_runtime_hls_job_audit
from adapter.deps import get_api, get_auth_store, get_desktop_agent_runtime
from backend.models.desktop_media_probe_cache import DesktopMediaProbeCache
from backend.models.enums import InstancePresence, MaterialSourceKind, SessionMode
from backend.models.errors import PreconditionFailure
from backend.models.media_stream_session import MediaStreamSession
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.desktop_media_hls import (
    build_hls_cache_key,
    current_hls_profile,
    hls_artifact_media_type,
    normalize_hls_artifact_path,
    prune_hls_cache,
)
from backend.system.desktop_agent_runtime import (
    DesktopAgentHlsJobNotFoundError,
    DesktopAgentNotConnectedError,
    DesktopAgentProbeClosedError,
    DesktopAgentProbeTimeoutError,
    DesktopAgentRuntime,
    DesktopAgentStreamClosedError,
    DesktopAgentStreamLimitError,
    DesktopAgentStreamTimeoutError,
)
from backend.system.material_paths import resolve_material_file_path
from backend.system.runtime_features import current_runtime_features, require_server_media_stream_enabled


router = APIRouter()


_CONTAINER_SUFFIX_MAP = {
    "m4v": "m4v",
    "mkv": "mkv",
    "mov": "mov",
    "mp4": "mp4",
    "webm": "webm",
}
_CONTAINER_FORMAT_MAP = {
    "matroska": "mkv",
    "mov": "mov",
    "mp4": "mp4",
    "mpegts": "ts",
    "webm": "webm",
}
_CODEC_ALIASES = {
    "avc": "h264",
    "avc1": "h264",
    "h265": "hevc",
    "hev1": "hevc",
    "mp4a": "aac",
    "x264": "h264",
    "x265": "hevc",
}
_MEDIA_ACCESS_TOKEN_QUERY_PARAM = "mediaAccessToken"
_MEDIA_ACCESS_TOKEN_VERSION = 1
_MEDIA_ACCESS_TOKEN_KIND_RELAY = "relay_file"
_MEDIA_ACCESS_TOKEN_KIND_HLS = "hls_artifact"
_MEDIA_ACCESS_TOKEN_FALLBACK_SECRET = secrets.token_urlsafe(32)
_HLS_URI_ATTR_PATTERN = re.compile(r'URI="([^"]+)"')


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _env_positive_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except Exception:
        return float(default)
    return float(default) if value <= 0 else value


def _agent_direct_max_mbps() -> float:
    return _env_positive_float("PLM_AGENT_DIRECT_MAX_MBPS", 3.0)


def _env_positive_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return int(default) if value <= 0 else int(value)


def _agent_progressive_max_height() -> int:
    return _env_positive_int("PLM_AGENT_PROGRESSIVE_MAX_HEIGHT", 2160)


def _agent_progressive_max_fps() -> float:
    return _env_positive_float("PLM_AGENT_PROGRESSIVE_MAX_FPS", 60.0)


def _agent_progressive_max_audio_channels() -> int:
    return _env_positive_int("PLM_AGENT_PROGRESSIVE_MAX_AUDIO_CHANNELS", 6)


def _media_access_token_ttl_seconds() -> int:
    return _env_positive_int("PLM_MEDIA_ACCESS_TOKEN_TTL_SECONDS", 14_400)


def _media_access_token_secret() -> bytes:
    raw = (os.getenv("PLM_MEDIA_ACCESS_TOKEN_SECRET") or "").strip()
    if raw:
        return raw.encode("utf-8")
    return _MEDIA_ACCESS_TOKEN_FALLBACK_SECRET.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    normalized = str(text).strip()
    if not normalized:
        raise ValueError("empty base64url payload")
    padding = "=" * ((4 - len(normalized) % 4) % 4)
    return base64.urlsafe_b64decode(normalized + padding)


def _sign_media_access_payload(payload_bytes: bytes) -> str:
    digest = hmac.new(_media_access_token_secret(), payload_bytes, hashlib.sha256).digest()
    return _b64url_encode(digest)


def _build_media_access_token(
    *,
    kind: str,
    user_id: str,
    project_id: str | None = None,
    instance_id: str | None = None,
    stream_id: str | None = None,
) -> str:
    expires_at = int(datetime.now(timezone.utc).timestamp()) + _media_access_token_ttl_seconds()
    payload = {
        "v": _MEDIA_ACCESS_TOKEN_VERSION,
        "k": str(kind),
        "u": str(user_id),
        "p": None if project_id is None else str(project_id),
        "i": None if instance_id is None else str(instance_id),
        "s": None if stream_id is None else str(stream_id),
        "e": expires_at,
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{_b64url_encode(payload_bytes)}.{_sign_media_access_payload(payload_bytes)}"


def _verify_media_access_token(
    token: str,
    *,
    kind: str,
    project_id: str | None = None,
    instance_id: str | None = None,
    stream_id: str | None = None,
) -> dict[str, object] | None:
    token_text = str(token or "").strip()
    if not token_text or "." not in token_text:
        return None
    payload_part, signature_part = token_text.split(".", 1)
    try:
        payload_bytes = _b64url_decode(payload_part)
        signature_bytes = _b64url_decode(signature_part)
    except Exception:
        return None
    expected_signature = hmac.new(_media_access_token_secret(), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature_bytes, expected_signature):
        return None
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("v") or 0) != _MEDIA_ACCESS_TOKEN_VERSION:
        return None
    if str(payload.get("k") or "").strip() != str(kind):
        return None
    if int(payload.get("e") or 0) < int(datetime.now(timezone.utc).timestamp()):
        return None
    if project_id is not None and str(payload.get("p") or "").strip() != str(project_id):
        return None
    if instance_id is not None and str(payload.get("i") or "").strip() != str(instance_id):
        return None
    if stream_id is not None and str(payload.get("s") or "").strip() != str(stream_id):
        return None
    if not str(payload.get("u") or "").strip():
        return None
    return payload


def _append_media_access_token(url: str, token: str | None) -> str:
    token_text = str(token or "").strip()
    if not token_text:
        return str(url)
    parts = urlsplit(str(url))
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != _MEDIA_ACCESS_TOKEN_QUERY_PARAM]
    query.append((_MEDIA_ACCESS_TOKEN_QUERY_PARAM, token_text))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _rewrite_hls_playlist_with_media_access_token(text: str, token: str) -> str:
    token_text = str(token or "").strip()
    if not token_text:
        return text
    ends_with_newline = text.endswith("\n")
    rewritten_lines: list[str] = []
    for line in text.splitlines():
        current = line
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            current = _append_media_access_token(stripped, token_text)
        elif "URI=" in current:
            current = _HLS_URI_ATTR_PATTERN.sub(
                lambda match: f'URI="{_append_media_access_token(match.group(1), token_text)}"',
                current,
            )
        rewritten_lines.append(current)
    rewritten = "\n".join(rewritten_lines)
    if ends_with_newline:
        rewritten += "\n"
    return rewritten


def _build_relay_media_url(
    *,
    base_url: str,
    request: Request,
    kind: str,
    project_id: str | None = None,
    instance_id: str | None = None,
    stream_id: str | None = None,
) -> str:
    if not current_runtime_features().auth_enabled:
        return str(base_url)
    viewer = get_request_auth_user(request)
    if viewer is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    token = _build_media_access_token(
        kind=kind,
        user_id=viewer.user_id,
        project_id=project_id,
        instance_id=instance_id,
        stream_id=stream_id,
    )
    return _append_media_access_token(base_url, token)


def _resolve_media_request_user_id(
    request: Request,
    auth_store: AuthStore,
    *,
    kind: str,
    project_id: str | None = None,
    instance_id: str | None = None,
    stream_id: str | None = None,
) -> tuple[str | None, str | None]:
    viewer = get_request_auth_user(request)
    if viewer is not None:
        return str(viewer.user_id), None
    if not current_runtime_features().auth_enabled:
        return None, None
    session_user = resolve_session_user(request, auth_store)
    if session_user is not None:
        return str(session_user.user_id), None
    media_access_token = str(request.query_params.get(_MEDIA_ACCESS_TOKEN_QUERY_PARAM, "")).strip()
    payload = _verify_media_access_token(
        media_access_token,
        kind=kind,
        project_id=project_id,
        instance_id=instance_id,
        stream_id=stream_id,
    )
    if payload is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return str(payload["u"]), media_access_token


def _normalize_probe_codec(value: object) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    return _CODEC_ALIASES.get(text, text)


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except Exception:
        return None
    return None if parsed < 0 else parsed


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except Exception:
        return None
    return None if parsed < 0 else parsed


def _normalize_probe_container(raw_value: object, *, relative_path: str) -> str:
    suffix = PurePath(str(relative_path)).suffix.lower().lstrip(".")
    mapped_suffix = _CONTAINER_SUFFIX_MAP.get(suffix)
    if mapped_suffix is not None:
        return mapped_suffix
    for token in str(raw_value or "").split(","):
        text = token.strip().lower()
        if not text:
            continue
        mapped = _CONTAINER_FORMAT_MAP.get(text)
        if mapped is not None:
            return mapped
        return text
    return "unknown"


def _probe_payload_to_cache(
    *,
    project_id: str,
    instance_id: str,
    agent_id: str,
    relative_path: str,
    payload: dict,
) -> DesktopMediaProbeCache:
    duration_ms = _coerce_optional_int(payload.get("durationMs"))
    if duration_ms is None and payload.get("durationSeconds") is not None:
        try:
            duration_ms = max(0, int(float(payload["durationSeconds"]) * 1000))
        except Exception:
            duration_ms = None
    cache = DesktopMediaProbeCache(
        project_id=str(project_id),
        instance_id=str(instance_id),
        agent_id=str(agent_id),
        container=_normalize_probe_container(payload.get("container"), relative_path=relative_path),
        video_codec=_normalize_probe_codec(payload.get("videoCodec")),
        audio_codec=_normalize_probe_codec(payload.get("audioCodec")),
        duration_ms=duration_ms,
        bitrate_bps=_coerce_optional_int(payload.get("bitrateBps")),
        width=_coerce_optional_int(payload.get("width")),
        height=_coerce_optional_int(payload.get("height")),
        fps=_coerce_optional_float(payload.get("fps")),
        audio_channels=_coerce_optional_int(payload.get("audioChannels")),
        audio_sample_rate=_coerce_optional_int(payload.get("audioSampleRate")),
        video_stream_count=_coerce_optional_int(payload.get("videoStreamCount")),
        audio_stream_count=_coerce_optional_int(payload.get("audioStreamCount")),
        subtitle_stream_count=_coerce_optional_int(payload.get("subtitleStreamCount")),
        size_bytes=_coerce_optional_int(payload.get("sizeBytes")),
        modified_at=None if payload.get("modifiedAt") is None else str(payload.get("modifiedAt")).strip() or None,
        updated_at=_utc_now_text(),
    )
    cache.validate_write_time()
    return cache


def _probe_cache_to_dto(probe: DesktopMediaProbeCache) -> dict[str, object]:
    return {
        "container": probe.container,
        "videoCodec": probe.video_codec,
        "audioCodec": probe.audio_codec,
        "durationMs": probe.duration_ms,
        "bitrateBps": probe.bitrate_bps,
        "width": probe.width,
        "height": probe.height,
        "fps": probe.fps,
        "audioChannels": probe.audio_channels,
        "audioSampleRate": probe.audio_sample_rate,
        "videoStreamCount": probe.video_stream_count,
        "audioStreamCount": probe.audio_stream_count,
        "subtitleStreamCount": probe.subtitle_stream_count,
        "sizeBytes": probe.size_bytes,
        "modifiedAt": probe.modified_at,
        "updatedAt": probe.updated_at,
    }


def _browser_family(request: Request | None) -> str:
    if request is None:
        return "generic"
    user_agent = (
        str(request.headers.get("X-Playback-Browser") or "").strip()
        or str(request.headers.get("User-Agent") or "").strip()
    ).lower()
    is_apple_platform = any(token in user_agent for token in ("iphone", "ipad", "ipod", "macintosh", "mac os x"))
    if "edg/" in user_agent:
        return "edge"
    if "chrome/" in user_agent or "chromium" in user_agent or "crios/" in user_agent:
        return "chromium"
    if "firefox/" in user_agent or "fxios/" in user_agent:
        return "firefox"
    if (
        is_apple_platform
        and "safari/" in user_agent
        and "chrome/" not in user_agent
        and "chromium" not in user_agent
        and "crios/" not in user_agent
    ):
        return "safari"
    return "generic"


def _progressive_profiles_for_browser(browser_family: str) -> dict[str, tuple[set[str], set[str]]]:
    family = str(browser_family or "generic").strip().lower()
    common_mp4 = {
        "mp4": ({"h264"}, {"aac", "mp3"}),
        "m4v": ({"h264"}, {"aac", "mp3"}),
    }
    if family == "safari":
        return {
            "mp4": ({"h264", "hevc"}, {"aac", "mp3", "ac3", "eac3"}),
            "m4v": ({"h264", "hevc"}, {"aac", "mp3", "ac3", "eac3"}),
            "mov": ({"h264", "hevc"}, {"aac", "mp3", "ac3", "eac3"}),
        }
    return {
        **common_mp4,
        "webm": ({"vp8", "vp9", "av1"}, {"opus", "vorbis"}),
    }


def _progressive_relay_decision_reason(probe: DesktopMediaProbeCache, *, browser_family: str = "generic") -> str:
    progressive_profiles = _progressive_profiles_for_browser(browser_family)
    generic_profiles = _progressive_profiles_for_browser("generic")
    profile = progressive_profiles.get(str(probe.container).lower())
    if profile is None:
        generic_profile = generic_profiles.get(str(probe.container).lower())
        if generic_profile is not None and str(browser_family).strip().lower() != "generic":
            return f"browser:{browser_family}/container:{probe.container}"
        return f"container:{probe.container}"
    allowed_video, allowed_audio = profile
    if probe.video_codec is None:
        return "video_codec:missing"
    normalized_video = str(probe.video_codec).lower()
    if normalized_video not in allowed_video:
        if str(browser_family).strip().lower() != "generic":
            return f"browser:{browser_family}/video_codec:{probe.video_codec}"
        return f"video_codec:{probe.video_codec}"
    if probe.audio_codec is not None and str(probe.audio_codec).lower() not in allowed_audio:
        if str(browser_family).strip().lower() != "generic":
            return f"browser:{browser_family}/audio_codec:{probe.audio_codec}"
        return f"audio_codec:{probe.audio_codec}"
    max_bitrate_bps = int(_agent_direct_max_mbps() * 1_000_000)
    if probe.bitrate_bps is not None and int(probe.bitrate_bps) > max_bitrate_bps:
        return f"bitrate:{probe.bitrate_bps}>{max_bitrate_bps}"
    if probe.height is not None and int(probe.height) > _agent_progressive_max_height():
        return f"height:{probe.height}>{_agent_progressive_max_height()}"
    if probe.fps is not None and float(probe.fps) > _agent_progressive_max_fps():
        return f"fps:{probe.fps}>{_agent_progressive_max_fps()}"
    if probe.audio_channels is not None and int(probe.audio_channels) > _agent_progressive_max_audio_channels():
        return f"audio_channels:{probe.audio_channels}>{_agent_progressive_max_audio_channels()}"
    if probe.subtitle_stream_count is not None and int(probe.subtitle_stream_count) > 0 and str(probe.container).lower() not in {"mp4", "m4v"}:
        return f"subtitle_streams:{probe.subtitle_stream_count}"
    return "progressive_supported"


def _supports_progressive_relay(probe: DesktopMediaProbeCache, *, browser_family: str = "generic") -> bool:
    return _progressive_relay_decision_reason(probe, browser_family=browser_family) == "progressive_supported"


def _hls_job_reason(job_state: str, job_message: str | None) -> str:
    state = str(job_state or "").strip().upper()
    message = str(job_message or "").strip()
    if state == "FAILED":
        return message or "transcode_failed"
    if state == "CANCELLED":
        return message or "transcode_cancelled"
    return "transcode_pending"


def _should_retry_terminal_hls_job(job_state: str, job_message: str | None = None) -> bool:
    del job_message
    # A cancelled HLS attempt should not poison future playback requests for the
    # same cache key. The next viewer request must be able to enqueue a fresh job.
    return str(job_state or "").strip().upper() == "CANCELLED"


def _persisted_terminal_hls_job_reason(auth_store: AuthStore, cache_key: str) -> str | None:
    audit = auth_store.get_latest_desktop_agent_hls_job_audit_by_cache_key(cache_key)
    if audit is None:
        return None
    state = str(audit.state).strip().upper()
    if state not in {"FAILED", "CANCELLED"}:
        return None
    if _should_retry_terminal_hls_job(state, audit.message):
        return None
    return _hls_job_reason(state, audit.message)


async def _get_or_probe_media_cache(
    *,
    project_id: str,
    instance_id: str,
    agent_id: str,
    agent_user_id: str,
    relative_path: str,
    auth_store: AuthStore,
    runtime: DesktopAgentRuntime,
) -> DesktopMediaProbeCache:
    cached = auth_store.get_desktop_media_probe_cache(project_id, instance_id, agent_id)
    if cached is not None:
        return cached
    probe_request = runtime.create_probe_request(
        agent_id=agent_id,
        project_id=project_id,
        instance_id=instance_id,
        relative_path=relative_path,
    )
    try:
        runtime.enqueue_command(
            agent_id,
            {
                "type": "probe.request",
                "requestId": probe_request.request_id,
                "projectId": project_id,
                "instanceId": instance_id,
                "relativePath": relative_path,
            },
        )
    except DesktopAgentNotConnectedError as exc:
        runtime.release_probe_request(probe_request.request_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    try:
        payload = await runtime.wait_for_probe_result(probe_request.request_id)
        item = _probe_payload_to_cache(
            project_id=project_id,
            instance_id=instance_id,
            agent_id=agent_id,
            relative_path=relative_path,
            payload=payload,
        )
        return auth_store.upsert_desktop_media_probe_cache(item)
    except DesktopAgentProbeTimeoutError as exc:
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent_id,
            user_id=agent_user_id,
            level="error",
            category="probe",
            event_type="probe_timed_out",
            message=str(exc),
            details={"requestId": probe_request.request_id},
            project_id=project_id,
            instance_id=instance_id,
            relative_path=relative_path,
        )
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except DesktopAgentProbeClosedError as exc:
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent_id,
            user_id=agent_user_id,
            level="error",
            category="probe",
            event_type="probe_closed",
            message=str(exc),
            details={"requestId": probe_request.request_id},
            project_id=project_id,
            instance_id=instance_id,
            relative_path=relative_path,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except PreconditionFailure as exc:
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent_id,
            user_id=agent_user_id,
            level="error",
            category="probe",
            event_type="probe_invalid",
            message=str(exc),
            details={"requestId": probe_request.request_id},
            project_id=project_id,
            instance_id=instance_id,
            relative_path=relative_path,
        )
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _parse_range_header(range_header: str | None) -> tuple[int | None, int | None]:
    raw = str(range_header or "").strip()
    if not raw:
        return None, None
    if not raw.lower().startswith("bytes="):
        raise HTTPException(status_code=416, detail="Unsupported Range header")
    spec = raw[6:].strip()
    if "," in spec:
        raise HTTPException(status_code=416, detail="Multiple ranges are not supported")
    start_text, separator, end_text = spec.partition("-")
    if separator != "-":
        raise HTTPException(status_code=416, detail="Malformed Range header")
    start_text = start_text.strip()
    end_text = end_text.strip()
    if not start_text and end_text:
        raise HTTPException(status_code=416, detail="Suffix byte ranges are not supported")
    try:
        start = None if not start_text else int(start_text)
        end = None if not end_text else int(end_text)
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Malformed Range header") from exc
    if start is None and end is None:
        raise HTTPException(status_code=416, detail="Empty Range header")
    if start is not None and start < 0:
        raise HTTPException(status_code=416, detail="Range start must be >= 0")
    if end is not None and end < 0:
        raise HTTPException(status_code=416, detail="Range end must be >= 0")
    if start is not None and end is not None and end < start:
        raise HTTPException(status_code=416, detail="Range end must be greater than or equal to range start")
    return start, end


@router.get("/projects/{projectId}/media/instances/{instanceId}/playback")
async def get_instance_playback_descriptor(
    projectId: str,
    instanceId: str,
    request: Request,
    prefer_hls: bool = Query(default=False, alias="preferHls"),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> dict:
    inst = api.get_instance(projectId, instanceId)  # type: ignore[arg-type]
    if getattr(inst, "presence", None) == InstancePresence.MISSING:
        raise PreconditionFailure("material is MISSING")

    binding = api.get_project_material_source_binding(projectId)  # type: ignore[arg-type]
    if binding.source_kind == MaterialSourceKind.DESKTOP_AGENT_MANIFEST:
        if binding.desktop_agent_id is None:
            raise PreconditionFailure("desktop agent binding is missing")
        agent = auth_store.get_desktop_agent(str(binding.desktop_agent_id))
        agent_connected = runtime.is_agent_connected(agent.agent_id)
        probe = auth_store.get_desktop_media_probe_cache(projectId, instanceId, agent.agent_id)
        if probe is None:
            if not agent_connected:
                raise PreconditionFailure("desktop agent is offline")
            probe = await _get_or_probe_media_cache(
                project_id=projectId,
                instance_id=instanceId,
                agent_id=agent.agent_id,
                agent_user_id=agent.user_id,
                relative_path=inst.material_id.as_posix(),
                auth_store=auth_store,
                runtime=runtime,
            )
        media_type, _ = mimetypes.guess_type(inst.material_id.as_posix())
        probe_dto = _probe_cache_to_dto(probe)
        browser_family = _browser_family(request)
        progressive_reason = _progressive_relay_decision_reason(probe, browser_family=browser_family)
        hls_reason = f"prefer_hls:{progressive_reason}" if prefer_hls else progressive_reason
        if prefer_hls or not _supports_progressive_relay(probe, browser_family=browser_family):
            prune_hls_cache(auth_store)
            hls_profile = current_hls_profile()
            cache_key = build_hls_cache_key(
                project_id=projectId,
                instance_id=instanceId,
                agent_id=agent.agent_id,
                profile=hls_profile,
            )
            master_entry = auth_store.get_hls_cache_entry(cache_key, "master.m3u8")
            if master_entry is not None and Path(master_entry.file_path).exists():
                runtime.record_hls_cache_lookup(hit=True)
                auth_store.touch_hls_cache_entry_access(cache_key, "master.m3u8")
                manifest_url = _build_relay_media_url(
                    base_url=f"/api/media/streams/{cache_key}/master.m3u8",
                    request=request,
                    kind=_MEDIA_ACCESS_TOKEN_KIND_HLS,
                    project_id=projectId,
                    stream_id=cache_key,
                )
                return {
                    "ok": True,
                    "data": {
                        "mode": "relay_hls",
                        "streamId": cache_key,
                        "manifestUrl": manifest_url,
                        "contentType": "application/vnd.apple.mpegurl",
                        "supportsRange": False,
                        "agentId": agent.agent_id,
                        "ready": True,
                        "probe": probe_dto,
                        "decisionReason": hls_reason,
                    },
                }
            runtime.record_hls_cache_lookup(hit=False)
            existing_job = runtime.get_hls_job_by_cache_key(cache_key)
            if (
                existing_job is not None
                and existing_job.state in {"FAILED", "CANCELLED"}
                and not _should_retry_terminal_hls_job(existing_job.state, existing_job.message)
            ):
                reason = _hls_job_reason(existing_job.state, existing_job.message)
                return {
                    "ok": True,
                    "data": {
                        "mode": "relay_hls",
                        "streamId": cache_key,
                        "contentType": media_type or "application/octet-stream",
                        "supportsRange": False,
                        "agentId": agent.agent_id,
                        "ready": False,
                        "reason": reason,
                        "probe": probe_dto,
                        "decisionReason": hls_reason,
                    },
                }
            persisted_reason = _persisted_terminal_hls_job_reason(auth_store, cache_key)
            if existing_job is None and persisted_reason is not None:
                return {
                    "ok": True,
                    "data": {
                        "mode": "relay_hls",
                        "streamId": cache_key,
                        "contentType": media_type or "application/octet-stream",
                        "supportsRange": False,
                        "agentId": agent.agent_id,
                        "ready": False,
                        "reason": persisted_reason,
                        "probe": probe_dto,
                        "decisionReason": hls_reason,
                    },
                }
            job, created = runtime.create_or_get_hls_job(
                cache_key=cache_key,
                agent_id=agent.agent_id,
                project_id=projectId,
                instance_id=instanceId,
                relative_path=inst.material_id.as_posix(),
                profile=hls_profile,
            )
            persist_runtime_hls_job_audit(auth_store, job)
            if created:
                record_desktop_agent_diagnostic_event(
                    auth_store,
                    agent_id=agent.agent_id,
                    user_id=agent.user_id,
                    level="info",
                    category="hls",
                    event_type="hls_job_requested",
                    message="Requested desktop agent HLS transcode",
                    details={"jobId": job.job_id, "cacheKey": cache_key, "decisionReason": hls_reason},
                    project_id=projectId,
                    instance_id=instanceId,
                    relative_path=inst.material_id.as_posix(),
                    created_at=job.created_at,
                )
                try:
                    runtime.enqueue_command(
                        agent.agent_id,
                        {
                            "type": "hls.start",
                            "jobId": job.job_id,
                            "projectId": projectId,
                            "instanceId": instanceId,
                            "relativePath": inst.material_id.as_posix(),
                            "profile": hls_profile,
                        },
                    )
                except DesktopAgentNotConnectedError as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc
            reason = _hls_job_reason(job.state, job.message)
            return {
                "ok": True,
                "data": {
                    "mode": "relay_hls",
                    "streamId": cache_key,
                    "contentType": media_type or "application/octet-stream",
                    "supportsRange": False,
                    "agentId": agent.agent_id,
                    "ready": False,
                    "reason": reason,
                    "probe": probe_dto,
                    "decisionReason": hls_reason,
                },
            }
        return {
            "ok": True,
            "data": {
                "mode": "relay_progressive",
                "url": _build_relay_media_url(
                    base_url=f"/api/projects/{projectId}/media/instances/{instanceId}/relay-file",
                    request=request,
                    kind=_MEDIA_ACCESS_TOKEN_KIND_RELAY,
                    project_id=projectId,
                    instance_id=instanceId,
                ),
                "contentType": media_type or "application/octet-stream",
                "supportsRange": True,
                "agentId": agent.agent_id,
                "probe": probe_dto,
                "decisionReason": progressive_reason,
            },
        }

    return {
        "ok": True,
        "data": {
            "mode": "direct_file",
            "url": f"/api/projects/{projectId}/media/instances/{instanceId}",
            "supportsRange": True,
        },
    }


@router.get("/projects/{projectId}/media/instances/{instanceId}")
def stream_instance_media(projectId: str, instanceId: str, api: SystemAPI = Depends(get_api)) -> FileResponse:
    require_server_media_stream_enabled()
    inst = api.get_instance(projectId, instanceId)  # type: ignore[arg-type]
    if getattr(inst, "presence", None) == InstancePresence.MISSING:
        raise PreconditionFailure("material is MISSING")

    s = api.begin_session(projectId, SessionMode.READ_ONLY)  # type: ignore[arg-type]
    try:
        storage_cfg = api.sys.project_storage_config_repo.get(s)
    finally:
        api.sys.rollback(s)

    p = resolve_material_file_path(storage_cfg, inst.material_id)

    if not p.exists():
        raise PreconditionFailure(f"material file not found: {p}")
    if not p.is_file():
        raise PreconditionFailure(f"material is not a file: {p}")

    media_type, _ = mimetypes.guess_type(str(p))
    return FileResponse(path=str(p), media_type=media_type or "application/octet-stream", filename=p.name)


@router.get("/projects/{projectId}/media/instances/{instanceId}/relay-file")
async def relay_instance_media(
    projectId: str,
    instanceId: str,
    request: Request,
    range: str | None = Header(default=None),
    api: SystemAPI = Depends(get_api),
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> Response:
    inst = api.get_instance(projectId, instanceId)  # type: ignore[arg-type]
    if getattr(inst, "presence", None) == InstancePresence.MISSING:
        raise PreconditionFailure("material is MISSING")

    binding = api.get_project_material_source_binding(projectId)  # type: ignore[arg-type]
    if binding.source_kind != MaterialSourceKind.DESKTOP_AGENT_MANIFEST or binding.desktop_agent_id is None:
        raise PreconditionFailure("project is not using desktop agent relay")

    agent = auth_store.get_desktop_agent(str(binding.desktop_agent_id))
    if not runtime.is_agent_connected(agent.agent_id):
        raise PreconditionFailure("desktop agent is offline")

    viewer_user_id, _ = _resolve_media_request_user_id(
        request,
        auth_store,
        kind=_MEDIA_ACCESS_TOKEN_KIND_RELAY,
        project_id=projectId,
        instance_id=instanceId,
    )
    if viewer_user_id is None:
        viewer_user_id = str(agent.user_id)
    elif not auth_store.user_has_project_access(viewer_user_id, projectId):
        raise HTTPException(status_code=403, detail="Project access denied")
    media_type, _ = mimetypes.guess_type(inst.material_id.as_posix())
    start, end = _parse_range_header(range)
    try:
        session = runtime.create_stream_session(
            agent_id=agent.agent_id,
            user_id=viewer_user_id,
            project_id=projectId,
            instance_id=instanceId,
            relative_path=inst.material_id.as_posix(),
            content_type=media_type or "application/octet-stream",
        )
    except DesktopAgentStreamLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    persisted_stream = auth_store.create_media_stream_session(
        MediaStreamSession(
            stream_id=session.stream_id,
            project_id=projectId,
            instance_id=instanceId,
            agent_id=agent.agent_id,
            user_id=viewer_user_id,
            mode="relay_progressive",
            status="OPENING",
            range_start=start,
            range_end=end,
            bytes_from_agent=0,
            bytes_to_viewer=0,
            created_at=session.created_at,
            updated_at=session.created_at,
            expires_at=session.expires_at,
        )
    )
    try:
        runtime.enqueue_command(
            agent.agent_id,
            {
                "type": "stream.open",
                "streamId": session.stream_id,
                "projectId": projectId,
                "instanceId": instanceId,
                "relativePath": inst.material_id.as_posix(),
                "rangeStart": start,
                "rangeEnd": end,
                "contentType": session.content_type,
            },
        )
        stream_headers = await runtime.wait_for_stream_headers(session.stream_id)
        auth_store.mark_media_stream_session_streaming(persisted_stream.stream_id)
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            level="info",
            category="relay",
            event_type="stream_opened",
            message="Desktop agent relay stream opened",
            details={"streamId": session.stream_id, "rangeStart": start, "rangeEnd": end},
            project_id=projectId,
            instance_id=instanceId,
            relative_path=inst.material_id.as_posix(),
            created_at=_utc_now_text(),
        )
    except DesktopAgentNotConnectedError as exc:
        auth_store.finalize_media_stream_session(persisted_stream.stream_id, status="FAILED", failure_reason=str(exc))
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            level="error",
            category="relay",
            event_type="stream_open_failed",
            message=str(exc),
            details={"streamId": session.stream_id},
            project_id=projectId,
            instance_id=instanceId,
            relative_path=inst.material_id.as_posix(),
        )
        runtime.release_stream_session(session.stream_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except DesktopAgentStreamTimeoutError as exc:
        auth_store.finalize_media_stream_session(persisted_stream.stream_id, status="FAILED", failure_reason=str(exc))
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            level="error",
            category="relay",
            event_type="stream_open_timed_out",
            message=str(exc),
            details={"streamId": session.stream_id},
            project_id=projectId,
            instance_id=instanceId,
            relative_path=inst.material_id.as_posix(),
        )
        runtime.release_stream_session(session.stream_id)
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except DesktopAgentStreamClosedError as exc:
        auth_store.finalize_media_stream_session(persisted_stream.stream_id, status="FAILED", failure_reason=str(exc))
        record_desktop_agent_diagnostic_event(
            auth_store,
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            level="error",
            category="relay",
            event_type="stream_open_failed",
            message=str(exc),
            details={"streamId": session.stream_id},
            project_id=projectId,
            instance_id=instanceId,
            relative_path=inst.material_id.as_posix(),
        )
        runtime.release_stream_session(session.stream_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response_headers = {
        "Accept-Ranges": "bytes",
    }
    requested_partial = start is not None or end is not None
    status_code = 206 if requested_partial else 200
    if stream_headers.file_size is not None and stream_headers.range_start is not None and stream_headers.range_end is not None:
        response_headers["Content-Length"] = str(stream_headers.range_end - stream_headers.range_start + 1)
    elif stream_headers.file_size is not None and not requested_partial:
        response_headers["Content-Length"] = str(stream_headers.file_size)
    if requested_partial and stream_headers.file_size is not None and stream_headers.range_start is not None and stream_headers.range_end is not None:
        response_headers["Content-Range"] = (
            f"bytes {stream_headers.range_start}-{stream_headers.range_end}/{stream_headers.file_size}"
        )

    async def _stream_body():
        try:
            async for chunk in runtime.iter_stream_content(session.stream_id):
                if await request.is_disconnected():
                    auth_store.finalize_media_stream_session(
                        persisted_stream.stream_id,
                        status="CANCELLED",
                        failure_reason="viewer disconnected during relay",
                    )
                    record_desktop_agent_diagnostic_event(
                        auth_store,
                        agent_id=agent.agent_id,
                        user_id=agent.user_id,
                        level="warning",
                        category="relay",
                        event_type="stream_cancelled",
                        message="viewer disconnected during relay",
                        details={"streamId": session.stream_id},
                        project_id=projectId,
                        instance_id=instanceId,
                        relative_path=inst.material_id.as_posix(),
                    )
                    runtime.cancel_stream_session(
                        session.stream_id,
                        reason="viewer disconnected during relay",
                        notify_agent=True,
                    )
                    return
                auth_store.add_media_stream_session_viewer_bytes(persisted_stream.stream_id, len(chunk))
                yield chunk
            auth_store.finalize_media_stream_session(persisted_stream.stream_id, status="COMPLETED")
            record_desktop_agent_diagnostic_event(
                auth_store,
                agent_id=agent.agent_id,
                user_id=agent.user_id,
                level="info",
                category="relay",
                event_type="stream_completed",
                message="Desktop agent relay stream completed",
                details={"streamId": session.stream_id},
                project_id=projectId,
                instance_id=instanceId,
                relative_path=inst.material_id.as_posix(),
            )
        except (DesktopAgentStreamClosedError, DesktopAgentStreamTimeoutError) as exc:
            auth_store.finalize_media_stream_session(persisted_stream.stream_id, status="FAILED", failure_reason=str(exc))
            record_desktop_agent_diagnostic_event(
                auth_store,
                agent_id=agent.agent_id,
                user_id=agent.user_id,
                level="error",
                category="relay",
                event_type="stream_failed",
                message=str(exc),
                details={"streamId": session.stream_id},
                project_id=projectId,
                instance_id=instanceId,
                relative_path=inst.material_id.as_posix(),
            )
            return
        finally:
            runtime.release_stream_session(session.stream_id)

    return StreamingResponse(
        _stream_body(),
        media_type=stream_headers.content_type,
        headers=response_headers,
        status_code=status_code,
    )


@router.get("/media/streams/{streamId}/{artifactPath:path}")
def get_hls_stream_artifact(
    streamId: str,
    artifactPath: str,
    request: Request,
    auth_store: AuthStore = Depends(get_auth_store),
    runtime: DesktopAgentRuntime = Depends(get_desktop_agent_runtime),
) -> FileResponse:
    prune_hls_cache(auth_store)
    normalized_artifact_path = normalize_hls_artifact_path(artifactPath)
    entry = auth_store.get_hls_cache_entry(streamId, normalized_artifact_path)
    if entry is None:
        raise HTTPException(status_code=404, detail="HLS artifact not found")
    viewer_user_id, media_access_token = _resolve_media_request_user_id(
        request,
        auth_store,
        kind=_MEDIA_ACCESS_TOKEN_KIND_HLS,
        project_id=entry.project_id,
        stream_id=streamId,
    )
    if viewer_user_id is not None and not auth_store.user_has_project_access(viewer_user_id, entry.project_id):
        raise HTTPException(status_code=403, detail="Project access denied")
    artifact_file = Path(entry.file_path)
    if not artifact_file.exists() or not artifact_file.is_file():
        raise HTTPException(status_code=404, detail="HLS artifact not found")
    auth_store.touch_hls_cache_entry_access(streamId, normalized_artifact_path)
    if media_access_token and normalized_artifact_path.lower().endswith(".m3u8"):
        playlist_text = artifact_file.read_text(encoding="utf-8")
        rewritten = _rewrite_hls_playlist_with_media_access_token(playlist_text, media_access_token)
        runtime.record_hls_artifact_served(size_bytes=len(rewritten.encode("utf-8")))
        return Response(
            content=rewritten,
            media_type=hls_artifact_media_type(normalized_artifact_path),
            headers={"Cache-Control": "private, max-age=60"},
        )
    runtime.record_hls_artifact_served(size_bytes=int(entry.size_bytes))
    return FileResponse(
        path=str(artifact_file),
        media_type=hls_artifact_media_type(normalized_artifact_path),
        filename=artifact_file.name,
        headers={"Cache-Control": "private, max-age=60"},
    )
