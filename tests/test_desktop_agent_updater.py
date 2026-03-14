from __future__ import annotations

import hashlib
from pathlib import Path

from desktop_agent.updater import DesktopAgentPreparedUpdate, DesktopAgentUpdater


class _StubResponse:
    def __init__(self, payload: dict | None = None, *, body: bytes = b"") -> None:
        self._payload = payload
        self._body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        assert self._payload is not None
        return self._payload

    def iter_content(self, chunk_size: int = 1024 * 1024):
        del chunk_size
        yield self._body


def test_desktop_agent_updater_returns_latest_download_url_and_metadata() -> None:
    requested_urls: list[tuple[str, bool]] = []

    def _request_get(url: str, *, timeout: float, stream: bool = False):
        requested_urls.append((url, stream))
        assert timeout == 5.0
        assert stream is False
        return _StubResponse(
            {
                "ok": True,
                "data": {
                    "available": True,
                    "requestedVersion": "0.1.0-beta.0",
                    "updateAvailable": True,
                    "latest": {
                        "version": "0.1.0-beta.1",
                        "publishedAt": "2026-03-11T12:00:00+00:00",
                        "releaseNotes": "Signed release",
                        "assetCount": 1,
                        "preferredAsset": {
                            "name": "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe",
                            "version": "0.1.0-beta.1",
                            "kind": "installer_exe",
                            "sizeBytes": 123,
                            "sha256": "abc",
                            "integrityMode": "sha256",
                            "publishedAt": "2026-03-11T12:00:00+00:00",
                            "downloadPath": "/api/system/desktop-agent-release/assets/LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe",
                            "signature": {"status": "SIGNED", "subject": "CN=LearningPyramid"},
                            "silentInstall": {"supported": True, "strategy": "inno_exe"},
                        },
                        "assets": [],
                    },
                },
            }
        )

    updater = DesktopAgentUpdater(request_get=_request_get, timeout_seconds=5)
    result = updater.check_for_updates(server_url="https://learn.example.com/", current_version="0.1.0-beta.0")

    assert requested_urls == [("https://learn.example.com/api/system/desktop-agent-release?currentVersion=0.1.0-beta.0", False)]
    assert result.available is True
    assert result.update_available is True
    assert result.latest_version == "0.1.0-beta.1"
    assert result.download_url == (
        "https://learn.example.com/api/system/desktop-agent-release/assets/"
        "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    )
    assert result.signature_status == "SIGNED"
    assert result.signature_subject == "CN=LearningPyramid"
    assert result.silent_install_supported is True
    assert result.silent_install_strategy == "inno_exe"
    assert result.release_notes == "Signed release"


def test_desktop_agent_updater_handles_missing_release() -> None:
    updater = DesktopAgentUpdater(
        request_get=lambda url, *, timeout, stream=False: _StubResponse(
            {"ok": True, "data": {"available": False, "requestedVersion": "0.1.0-beta.1", "updateAvailable": False, "latest": None}}
        )
    )

    result = updater.check_for_updates(server_url="https://learn.example.com", current_version="0.1.0-beta.1")

    assert result.available is False
    assert result.update_available is False
    assert result.download_url is None


def test_desktop_agent_updater_prepares_update_and_verifies_sha256(tmp_path: Path) -> None:
    asset_body = b"desktop-agent-installer"
    asset_sha256 = hashlib.sha256(asset_body).hexdigest()
    requested_urls: list[tuple[str, bool]] = []

    def _request_get(url: str, *, timeout: float, stream: bool = False):
        requested_urls.append((url, stream))
        if stream:
            assert timeout >= 30.0
            return _StubResponse(body=asset_body)
        return _StubResponse(
            {
                "ok": True,
                "data": {
                    "available": True,
                    "requestedVersion": "0.1.0-beta.0",
                    "updateAvailable": True,
                    "latest": {
                        "version": "0.1.0-beta.1",
                        "publishedAt": "2026-03-11T12:00:00+00:00",
                        "assetCount": 1,
                        "preferredAsset": {
                            "name": "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe",
                            "version": "0.1.0-beta.1",
                            "kind": "installer_exe",
                            "sizeBytes": len(asset_body),
                            "sha256": asset_sha256,
                            "integrityMode": "sha256",
                            "publishedAt": "2026-03-11T12:00:00+00:00",
                            "downloadPath": "/api/system/desktop-agent-release/assets/LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe",
                            "signature": {"status": "SIGNED", "subject": "CN=LearningPyramid"},
                            "silentInstall": {"supported": True, "strategy": "inno_exe"},
                        },
                        "assets": [],
                    },
                },
            }
        )

    updater = DesktopAgentUpdater(request_get=_request_get, timeout_seconds=5)
    prepared = updater.prepare_update(
        server_url="https://learn.example.com",
        current_version="0.1.0-beta.0",
        target_dir=tmp_path,
        require_signed=True,
    )

    assert requested_urls == [
        ("https://learn.example.com/api/system/desktop-agent-release?currentVersion=0.1.0-beta.0", False),
        (
            "https://learn.example.com/api/system/desktop-agent-release/assets/LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe",
            True,
        ),
    ]
    assert prepared.latest_version == "0.1.0-beta.1"
    assert prepared.asset_path.read_bytes() == asset_body
    assert prepared.sha256 == asset_sha256
    assert prepared.signature_status == "SIGNED"
    assert prepared.silent_install_supported is True


def test_desktop_agent_updater_builds_silent_install_plan(tmp_path: Path) -> None:
    asset_path = tmp_path / "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    asset_path.write_bytes(b"installer")
    prepared = DesktopAgentPreparedUpdate(
        current_version="0.1.0-beta.0",
        latest_version="0.1.0-beta.1",
        download_url="https://learn.example.com/download/agent.exe",
        asset_name=asset_path.name,
        asset_kind="installer_exe",
        asset_path=asset_path,
        sha256="abc123",
        integrity_mode="sha256",
        signature_status="SIGNED",
        signature_subject="CN=LearningPyramid",
        silent_install_supported=True,
        silent_install_strategy="inno_exe",
    )

    updater = DesktopAgentUpdater()
    plan = updater.build_silent_install_plan(prepared, current_pid=4321, helper_dir=tmp_path / "helper", relaunch=True)

    assert plan.command[0] == "powershell"
    assert str(plan.helper_script_path) in plan.command
    assert plan.rollback_script_path.exists()
    assert plan.state_path.name == "update-state.json"
    assert plan.backup_dir.name == "backup-current"
    helper_text = plan.helper_script_path.read_text(encoding="utf-8")
    assert "/VERYSILENT" in helper_text
    assert "healthcheck" in helper_text
    assert "Restore-Backup" in helper_text
