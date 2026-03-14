from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from threading import Event

from desktop_agent.errors import DesktopAgentTaskCancelled
from desktop_agent.path_safety import resolve_agent_media_path


def _ffmpeg_creationflags() -> int:
    if os.name != "nt":
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def transcode_media_to_hls(
    root_dir: str | Path,
    relative_path: str,
    *,
    height_max: int,
    video_bitrate: str,
    audio_bitrate: str,
    segment_seconds: int,
    cancel_event: Event | None = None,
) -> tuple[Path, tuple[Path, ...]]:
    source_file = resolve_agent_media_path(root_dir, relative_path)
    temp_dir = Path(tempfile.mkdtemp(prefix="learningpyramid-hls-")).resolve()
    playlist_path = temp_dir / "index.m3u8"
    segment_pattern = temp_dir / "segment%03d.ts"
    master_path = temp_dir / "master.m3u8"
    ffmpeg_log_path = temp_dir / "ffmpeg.log"
    process: subprocess.Popen[str] | None = None
    try:
        with ffmpeg_log_path.open("w", encoding="utf-8", errors="replace", newline="\n") as ffmpeg_log:
            try:
                process = subprocess.Popen(
                    [
                        "ffmpeg",
                        "-nostdin",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(source_file),
                        "-vf",
                        f"scale=-2:{int(height_max)}:force_original_aspect_ratio=decrease",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-b:v",
                        str(video_bitrate),
                        "-c:a",
                        "aac",
                        "-b:a",
                        str(audio_bitrate),
                        "-f",
                        "hls",
                        "-hls_time",
                        str(int(segment_seconds)),
                        "-hls_playlist_type",
                        "vod",
                        "-hls_segment_filename",
                        str(segment_pattern),
                        str(playlist_path),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=ffmpeg_log,
                    stderr=subprocess.STDOUT,
                    creationflags=_ffmpeg_creationflags(),
                )
            except FileNotFoundError as exc:
                raise RuntimeError("ffmpeg executable not found") from exc
            started_at = time.monotonic()
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    process.kill()
                    process.wait(timeout=5)
                    raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled")
                if process.poll() is not None:
                    break
                if time.monotonic() - started_at >= 3600:
                    process.kill()
                    process.wait(timeout=5)
                    raise RuntimeError("ffmpeg timed out")
                time.sleep(0.2)
            process.wait(timeout=5)
        if int(process.returncode or 0) != 0:
            raise RuntimeError(f"ffmpeg failed: {_read_text_file(ffmpeg_log_path) or process.returncode}")
        master_path.write_text(
            "\n".join(
                (
                    "#EXTM3U",
                    "#EXT-X-VERSION:3",
                    f'#EXT-X-STREAM-INF:BANDWIDTH=2000000,RESOLUTION=1280x{int(height_max)}',
                    "index.m3u8",
                    "",
                )
            ),
            encoding="utf-8",
        )
        artifacts = tuple(sorted(path for path in temp_dir.rglob("*") if path.is_file()))
        return temp_dir, artifacts
    except Exception:
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
