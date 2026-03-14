from __future__ import annotations

import time
from pathlib import Path

import pytest

from desktop_agent.config_store import AgentConfig
from desktop_agent.manifest_scan import scan_media_manifest
from desktop_agent.path_safety import resolve_agent_media_path
from desktop_agent.relay_client import RelayClient


def _create_client(root_dir: Path) -> RelayClient:
    return RelayClient(
        AgentConfig(
            server_url="http://127.0.0.1:8000",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(root_dir),
            device_name="BYLOU-PC",
        )
    )


def test_scan_media_manifest_skips_hidden_files_and_shortcuts(tmp_path: Path) -> None:
    root = tmp_path / "media"
    nested = root / "course-1"
    nested.mkdir(parents=True)
    (root / "lesson-01.mp4").write_bytes(b"video-a")
    (nested / "lesson-02.mkv").write_bytes(b"video-b")
    (root / ".hidden.mp4").write_bytes(b"hidden")
    (root / "lesson-03.mp4.lnk").write_text("shortcut", encoding="utf-8")

    entries = scan_media_manifest(root)

    assert [item["relativePath"] for item in entries] == [
        "course-1/lesson-02.mkv",
        "lesson-01.mp4",
    ]


def test_resolve_agent_media_path_rejects_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (tmp_path / "outside.mp4").write_bytes(b"outside")

    with pytest.raises(ValueError, match=r"must not contain '\.\.'"):
        resolve_agent_media_path(root, "../outside.mp4")


def test_resolve_agent_media_path_rejects_shortcut_files(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (root / "lesson-01.mp4.lnk").write_text("shortcut", encoding="utf-8")

    with pytest.raises(RuntimeError, match="shortcut path is not supported"):
        resolve_agent_media_path(root, "lesson-01.mp4.lnk")


def test_resolve_agent_media_path_rejects_symlinked_files_when_supported(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    target = root / "lesson-01.mp4"
    target.write_bytes(b"video")
    link = root / "linked-lesson.mp4"
    try:
        link.symlink_to(target)
    except (NotImplementedError, OSError):
        pytest.skip("symlink creation is not supported in this environment")

    with pytest.raises(RuntimeError, match="symlink path is not supported"):
        resolve_agent_media_path(root, "linked-lesson.mp4")


def test_relay_client_stream_open_rejects_parent_escape(tmp_path: Path) -> None:
    root = tmp_path / "media"
    root.mkdir()
    (tmp_path / "outside.mp4").write_bytes(b"outside")
    client = _create_client(root)

    client._handle_stream_open(
        {
            "streamId": "stream_123",
            "relativePath": "../outside.mp4",
            "contentType": "video/mp4",
            "rangeStart": 0,
            "rangeEnd": 3,
        }
    )

    deadline = time.monotonic() + 1
    while time.monotonic() < deadline and client._active_task_counts()["stream"] != 0:
        time.sleep(0.01)

    with pytest.raises(ValueError, match=r"must not contain '\.\.'"):
        client._raise_background_error_if_any()
