from __future__ import annotations

import json

from backend.models.study_material import StudyMaterial, StudyMaterialType
from backend.models.types import ProjectId, now_utc_ms
from backend.system.persistence_json import _decode_study_material, _encode_study_material
from tools.backup_runtime_bundle import backup_runtime_bundle, verify_runtime_bundle
from tools.restore_runtime_bundle import restore_runtime_bundle

from tests.fixtures.data_safety_runtime import create_project_media


def test_runtime_backup_restore_task_marker() -> None:
    assert True


def test_decode_study_material_accepts_legacy_compatibility_project_id() -> None:
    for legacy_key in ("compatibilityProjectId", "compatibility_project_id"):
        material = _decode_study_material(
            {
                "subjectId": "subject_legacy",
                "materialId": "legacy_main",
                "materialType": "COURSE",
                "title": "旧网课材料",
                "createdAtMs": 0,
                legacy_key: "subject_legacy",
            }
        )

        assert material.project_id == ProjectId("subject_legacy")
        assert not hasattr(material, "compatibility_project_id")


def test_encode_study_material_writes_project_id_without_compatibility_project_id() -> None:
    material = StudyMaterial(
        subject_id=ProjectId("subject_current"),
        material_id="book_1",
        material_type=StudyMaterialType.BOOK,
        title="当前书本材料",
        created_at=now_utc_ms(),
        project_id=ProjectId("project_book_1"),
    )

    payload = _encode_study_material(material)

    assert payload["projectId"] == "project_book_1"
    assert "compatibilityProjectId" not in payload


def test_backup_manifest_includes_media_checksums(tmp_path) -> None:
    media_root = tmp_path / "data"
    media_file = create_project_media(media_root, project_id="proj_000001", asset_id="asset_000001")
    bundle_path = tmp_path / "runtime-backup.json"

    backup_runtime_bundle(output_path=bundle_path, include_media=True, media_roots=(media_root,), verify=True)

    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    manifest = payload["manifest"]
    media_key = str(media_file.relative_to(media_root)).replace("\\", "/")
    assert manifest["schemaVersion"] == 2
    assert manifest["media"]["fileCount"] == 1
    assert media_key in manifest["media"]["checksums"]
    assert media_key in payload["mediaPayload"]


def test_verify_runtime_bundle_rejects_missing_media_payload(tmp_path) -> None:
    bundle_path = tmp_path / "runtime-backup.json"
    bundle_path.write_text(
        json.dumps(
            {
                "manifest": {
                    "schemaVersion": 2,
                    "media": {"fileCount": 1, "totalBytes": 3, "checksums": {"proj/media/a.png": "sha256:test"}},
                },
                "metadata": {},
                "storeSnapshot": {},
                "authSnapshot": {},
                "mediaPayload": {},
            }
        ),
        encoding="utf-8",
    )

    report = verify_runtime_bundle(bundle_path)

    assert report["state"] == "failed"
    assert "missing media payload" in report["errors"][0]


def test_restore_dry_run_reports_required_confirmation_without_writing_media(tmp_path) -> None:
    source_root = tmp_path / "source"
    create_project_media(source_root, project_id="proj_000001", asset_id="asset_000001")
    bundle_path = tmp_path / "runtime-backup.json"
    target_root = tmp_path / "target"
    backup_runtime_bundle(output_path=bundle_path, include_media=True, media_roots=(source_root,), verify=True)

    plan = restore_runtime_bundle(input_path=bundle_path, dry_run=True, target_media_root=target_root, restore_runtime_data=False)

    assert plan["requiresConfirmation"] is True
    assert plan["mediaFiles"] == 1
    assert not (target_root / "proj_000001" / "media" / "asset_000001.png").exists()


def test_restore_requires_confirmation_and_restores_media_payload(tmp_path) -> None:
    source_root = tmp_path / "source"
    create_project_media(source_root, project_id="proj_000001", asset_id="asset_000001")
    bundle_path = tmp_path / "runtime-backup.json"
    target_root = tmp_path / "target"
    backup_runtime_bundle(output_path=bundle_path, include_media=True, media_roots=(source_root,), verify=True)

    try:
        restore_runtime_bundle(input_path=bundle_path, target_media_root=target_root, restore_runtime_data=False)
    except ValueError as exc:
        assert "--confirm-replace" in str(exc)
    else:
        raise AssertionError("restore should require explicit confirmation")

    report = restore_runtime_bundle(input_path=bundle_path, confirm_replace=True, target_media_root=target_root, restore_runtime_data=False)

    restored = target_root / "proj_000001" / "media" / "asset_000001.png"
    assert restored.read_bytes() == b"fake-png"
    assert report["applied"]["mediaFiles"] == 1
