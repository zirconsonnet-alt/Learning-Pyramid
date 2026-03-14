from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from desktop_agent.transcode import transcode_media_to_hls


def test_transcode_media_to_hls_launches_ffmpeg_without_pipe_deadlock(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "lesson-01.mkv").write_bytes(b"video-bytes")
    captured: dict[str, object] = {}

    class _FakeProcess:
        returncode = 0

        def poll(self) -> int:
            return 0

        def wait(self, timeout: float | None = None) -> int:
            return 0

        def kill(self) -> None:
            raise AssertionError("kill should not be called")

    def _fake_popen(command: list[str], **kwargs):
        captured["command"] = list(command)
        captured["kwargs"] = dict(kwargs)
        segment_pattern = Path(str(command[command.index("-hls_segment_filename") + 1]))
        playlist_path = Path(str(command[-1]))
        playlist_path.write_text("#EXTM3U\n", encoding="utf-8")
        Path(str(segment_pattern).replace("%03d", "000")).write_bytes(b"segment")
        return _FakeProcess()

    monkeypatch.setattr("desktop_agent.transcode.subprocess.Popen", _fake_popen)

    output_dir, artifacts = transcode_media_to_hls(
        media_root,
        "lesson-01.mkv",
        height_max=720,
        video_bitrate="1800k",
        audio_bitrate="128k",
        segment_seconds=6,
    )

    command = captured["command"]
    kwargs = captured["kwargs"]
    assert isinstance(command, list)
    assert "-nostdin" in command
    assert "-hide_banner" in command
    assert command[command.index("-loglevel") + 1] == "error"
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.STDOUT
    assert kwargs["stdout"] is not subprocess.PIPE
    assert kwargs["creationflags"] == (
        int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
    )
    assert output_dir.name.startswith("learningpyramid-hls-")
    assert {item.name for item in artifacts} >= {"index.m3u8", "master.m3u8", "segment000.ts"}


def test_transcode_media_to_hls_surfaces_ffmpeg_log_output(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "lesson-01.mkv").write_bytes(b"video-bytes")

    class _FakeProcess:
        returncode = 1

        def poll(self) -> int:
            return 1

        def wait(self, timeout: float | None = None) -> int:
            return 1

        def kill(self) -> None:
            raise AssertionError("kill should not be called")

    def _fake_popen(command: list[str], **kwargs):
        log_handle = kwargs["stdout"]
        log_handle.write("Invalid data found when processing input\n")
        log_handle.flush()
        return _FakeProcess()

    monkeypatch.setattr("desktop_agent.transcode.subprocess.Popen", _fake_popen)

    with pytest.raises(RuntimeError, match="Invalid data found when processing input"):
        transcode_media_to_hls(
            media_root,
            "lesson-01.mkv",
            height_max=720,
            video_bitrate="1800k",
            audio_bitrate="128k",
            segment_seconds=6,
        )
