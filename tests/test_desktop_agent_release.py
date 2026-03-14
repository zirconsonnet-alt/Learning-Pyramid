from __future__ import annotations

import json
from pathlib import Path

from backend.system.desktop_agent_release import get_latest_desktop_agent_release, resolve_desktop_agent_release_asset
from backend.system.versioning import compare_versions


def test_compare_versions_orders_prerelease_and_final() -> None:
    assert compare_versions("0.1.0-beta.1", "0.1.0-beta.2") < 0
    assert compare_versions("0.1.0-beta.2", "0.1.0-rc.1") < 0
    assert compare_versions("0.1.0-rc.1", "0.1.0") < 0
    assert compare_versions("0.1.0", "0.1.0") == 0


def test_desktop_agent_release_selects_latest_version_and_merges_manifest_metadata(monkeypatch, tmp_path: Path) -> None:
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-windows-standalone.zip").write_bytes(b"standalone")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-windows-installer.zip").write_bytes(b"installer-zip")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe").write_bytes(b"installer-exe")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.0-Setup.exe").write_bytes(b"older-installer")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-release.json").write_text(
        json.dumps(
            {
                "version": "0.1.0-beta.1",
                "releaseNotes": "Signed installer release.",
                "assets": {
                    "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe": {
                        "signature": {
                            "status": "SIGNED",
                            "subject": "CN=LearningPyramid",
                            "thumbprint": "ABC123",
                            "signedAt": "2026-03-11T12:00:00+00:00",
                            "source": "signtool",
                        },
                        "silentInstall": {
                            "supported": True,
                            "strategy": "inno_exe",
                            "relaunch": True,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLM_DESKTOP_AGENT_RELEASE_DIR", str(release_dir))

    payload = get_latest_desktop_agent_release(current_version="0.1.0-beta.0")

    assert payload["available"] is True
    assert payload["updateAvailable"] is True
    assert payload["latest"]["version"] == "0.1.0-beta.1"
    assert payload["latest"]["assetCount"] == 3
    assert payload["latest"]["releaseNotes"] == "Signed installer release."
    assert payload["latest"]["preferredAsset"]["kind"] == "installer_exe"
    assert payload["latest"]["preferredAsset"]["signature"]["status"] == "SIGNED"
    assert payload["latest"]["preferredAsset"]["signature"]["subject"] == "CN=LearningPyramid"
    assert payload["latest"]["preferredAsset"]["silentInstall"]["supported"] is True
    assert payload["latest"]["preferredAsset"]["downloadPath"].endswith(
        "/api/system/desktop-agent-release/assets/LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    )
    assert resolve_desktop_agent_release_asset("LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe") == (
        release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    ).resolve()


def test_desktop_agent_release_signed_only_policy_filters_unsigned_assets(monkeypatch, tmp_path: Path) -> None:
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    signed_setup = release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    signed_setup.write_bytes(b"installer-exe")
    unsigned_standalone = release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-windows-standalone.zip"
    unsigned_standalone.write_bytes(b"standalone")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-release.json").write_text(
        json.dumps(
            {
                "version": "0.1.0-beta.1",
                "assets": {
                    signed_setup.name: {
                        "signature": {
                            "status": "SIGNED",
                            "subject": "CN=LearningPyramid",
                            "thumbprint": "ABC123",
                            "signedAt": "2026-03-11T12:00:00+00:00",
                            "source": "signtool",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLM_DESKTOP_AGENT_RELEASE_DIR", str(release_dir))
    monkeypatch.setenv("PLM_DESKTOP_AGENT_RELEASE_REQUIRE_SIGNED", "true")

    payload = get_latest_desktop_agent_release(current_version="0.1.0-beta.0")

    assert payload["available"] is True
    assert payload["policy"] == {
        "requireSigned": True,
        "acceptedSignatureStatuses": ["SIGNED"],
        "rejectedAssetCount": 1,
        "visibleAssetCount": 1,
        "totalAssetCount": 2,
    }
    assert payload["latest"]["assetCount"] == 1
    assert payload["latest"]["preferredAsset"]["name"] == signed_setup.name
    assert [item["name"] for item in payload["latest"]["assets"]] == [signed_setup.name]
    assert resolve_desktop_agent_release_asset(unsigned_standalone.name) is None
    assert resolve_desktop_agent_release_asset(signed_setup.name) == signed_setup.resolve()
