from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from desktop_agent.local_diagnostics import collect_media_file_stat_details, resolve_media_tool_path
from desktop_agent.path_safety import resolve_agent_media_path


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


def _parse_rate_to_float(value: object) -> float | None:
    text = str(value or "").strip()
    if not text or text in {"0/0", "N/A"}:
        return None
    left, separator, right = text.partition("/")
    if separator != "/":
        return _coerce_optional_float(text)
    try:
        numerator = float(left)
        denominator = float(right)
    except Exception:
        return None
    if denominator <= 0:
        return None
    parsed = numerator / denominator
    return None if parsed < 0 else round(parsed, 3)


def _normalize_container(format_name: object, file_path: Path) -> str:
    suffix = file_path.suffix.lower().lstrip(".")
    if suffix in {"m4v", "mkv", "mov", "mp4", "webm"}:
        return suffix
    for token in str(format_name or "").split(","):
        text = token.strip().lower()
        if not text:
            continue
        if text == "matroska":
            return "mkv"
        return text
    return "unknown"


def _fallback_probe_payload(file_path: Path, *, error: str | None = None) -> dict[str, Any]:
    stat_details = collect_media_file_stat_details(file_path)
    payload: dict[str, Any] = {
        "container": _normalize_container("", file_path),
        "videoCodec": None,
        "audioCodec": None,
        "durationMs": None,
        "bitrateBps": None,
        "width": None,
        "height": None,
        "fps": None,
        "audioChannels": None,
        "audioSampleRate": None,
        "videoStreamCount": 0,
        "audioStreamCount": 0,
        "subtitleStreamCount": 0,
        "sizeBytes": stat_details.get("sizeBytes"),
        "modifiedAt": stat_details.get("modifiedAt"),
        "ffprobePath": resolve_media_tool_path("ffprobe"),
    }
    if error:
        payload["error"] = str(error)
    return payload


def probe_media_file(root_dir: str | Path, relative_path: str) -> dict[str, Any]:
    file_path = resolve_agent_media_path(root_dir, relative_path)
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=format_name,duration,bit_rate:stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,channels,sample_rate",
                "-of",
                "json",
                str(file_path),
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return _fallback_probe_payload(file_path, error="ffprobe executable not found")
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("ffprobe timed out") from exc
    except subprocess.CalledProcessError as exc:
        stderr = str(exc.stderr or "").strip()
        raise RuntimeError(f"ffprobe failed: {stderr or exc.returncode}") from exc

    payload = json.loads(completed.stdout or "{}")
    format_info = dict(payload.get("format") or {})
    streams = list(payload.get("streams") or [])
    video_stream = next((item for item in streams if str(item.get("codec_type", "")).lower() == "video"), None)
    audio_stream = next((item for item in streams if str(item.get("codec_type", "")).lower() == "audio"), None)
    video_stream_count = sum(1 for item in streams if str(item.get("codec_type", "")).lower() == "video")
    audio_stream_count = sum(1 for item in streams if str(item.get("codec_type", "")).lower() == "audio")
    subtitle_stream_count = sum(1 for item in streams if str(item.get("codec_type", "")).lower() == "subtitle")
    duration_ms = None
    duration_raw = format_info.get("duration")
    if duration_raw not in (None, ""):
        try:
            duration_ms = max(0, int(float(str(duration_raw)) * 1000))
        except Exception:
            duration_ms = None
    stat_details = collect_media_file_stat_details(file_path)
    fps = None
    if video_stream is not None:
        fps = _parse_rate_to_float(video_stream.get("avg_frame_rate"))
        if fps is None:
            fps = _parse_rate_to_float(video_stream.get("r_frame_rate"))
    return {
        "container": _normalize_container(format_info.get("format_name"), file_path),
        "videoCodec": None if video_stream is None else str(video_stream.get("codec_name") or "").strip().lower() or None,
        "audioCodec": None if audio_stream is None else str(audio_stream.get("codec_name") or "").strip().lower() or None,
        "durationMs": duration_ms,
        "bitrateBps": _coerce_optional_int(format_info.get("bit_rate")),
        "width": None if video_stream is None else _coerce_optional_int(video_stream.get("width")),
        "height": None if video_stream is None else _coerce_optional_int(video_stream.get("height")),
        "fps": fps,
        "audioChannels": None if audio_stream is None else _coerce_optional_int(audio_stream.get("channels")),
        "audioSampleRate": None if audio_stream is None else _coerce_optional_int(audio_stream.get("sample_rate")),
        "videoStreamCount": video_stream_count,
        "audioStreamCount": audio_stream_count,
        "subtitleStreamCount": subtitle_stream_count,
        "sizeBytes": stat_details.get("sizeBytes"),
        "modifiedAt": stat_details.get("modifiedAt"),
        "ffprobePath": resolve_media_tool_path("ffprobe"),
    }
