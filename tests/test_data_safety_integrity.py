from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.system.data_safety import scan_media_references

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_scan_media_references_reports_missing_assets_with_identifiers(tmp_path) -> None:
    missing = tmp_path / "proj_000001" / "media" / "asset_000001.png"

    findings = scan_media_references(
        [
            {
                "projectId": "proj_000001",
                "assetId": "asset_000001",
                "expectedPath": str(missing),
                "referencedBy": "rp_000001",
            }
        ]
    )

    assert findings[0].code == "MEDIA_FILE_MISSING"
    assert findings[0].affected_entity_ids == ("proj_000001", "asset_000001", "rp_000001")


def test_scan_media_references_reports_orphaned_media_files(tmp_path) -> None:
    media = tmp_path / "proj_000001" / "media" / "asset_orphan.png"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"orphan")

    findings = scan_media_references([], media_roots=(tmp_path,))

    assert findings[0].code == "MEDIA_FILE_ORPHANED"
    assert findings[0].expected_location == str(media)


def test_check_data_safety_cli_outputs_json_findings(tmp_path) -> None:
    missing = tmp_path / "proj_000001" / "media" / "asset_000001.png"
    refs = tmp_path / "refs.json"
    refs.write_text(
        json.dumps(
            [
                {
                    "projectId": "proj_000001",
                    "assetId": "asset_000001",
                    "expectedPath": str(missing),
                    "referencedBy": "rp_000001",
                }
            ]
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "tools/check_data_safety.py", "--media-references", str(refs), "--json"],
        check=False,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["state"] == "blocked"
    assert payload["findings"][0]["code"] == "MEDIA_FILE_MISSING"
