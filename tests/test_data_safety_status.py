from __future__ import annotations

from backend.system.data_safety import (
    DataSafetyFinding,
    DataSafetyState,
    build_default_protected_data_classes,
    collect_data_safety_status,
)
from adapter.main import create_app
from fastapi.testclient import TestClient
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_default_protected_data_inventory_includes_database_and_media_classes() -> None:
    classes = build_default_protected_data_classes()
    ids = {item.id for item in classes}

    assert "auth-users" in ids
    assert "project-store" in ids
    assert "media-assets" in ids
    assert next(item for item in classes if item.id == "media-assets").storage_kind == "filesystem"


def test_data_safety_status_blocks_release_for_blocking_findings() -> None:
    status = collect_data_safety_status(
        findings=[
            DataSafetyFinding(
                severity="blocking",
                code="PROTECTED_PATH_MISSING",
                message="protected path missing",
                protected_class_id="media-assets",
                affected_entity_ids=("media-assets",),
                expected_location="/app/data",
                observed_state="missing",
                recommended_action="restore persistent mount",
            )
        ]
    )

    assert status.state == DataSafetyState.BLOCKED
    assert status.release_blocked is True
    assert status.findings[0].code == "PROTECTED_PATH_MISSING"


def test_data_safety_status_reports_unknown_when_storage_cannot_be_checked() -> None:
    status = collect_data_safety_status(storage_check_available=False)

    assert status.state == DataSafetyState.UNKNOWN
    assert status.release_blocked is True
    assert status.findings[0].code == "DATA_SAFETY_UNKNOWN"


def test_data_safety_status_serializes_for_api_contract() -> None:
    status = collect_data_safety_status()

    payload = status.to_api_dict()

    assert payload["state"] == "ok"
    assert payload["releaseBlocked"] is False
    assert any(item["id"] == "media-assets" for item in payload["protectedClasses"])
    assert payload["findings"] == []


def test_system_data_safety_endpoint_returns_operator_status() -> None:
    client = TestClient(create_app())

    resp = client.get("/api/system/data-safety")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["data"]["state"] in {"ok", "warning", "blocked", "unknown"}
    assert "releaseBlocked" in body["data"]


def test_projects_page_surfaces_blocked_or_unknown_data_safety_state() -> None:
    projects_page = (REPO_ROOT / "frontend" / "src" / "views" / "projects" / "ProjectsPage.tsx").read_text(encoding="utf-8")
    system_api = (REPO_ROOT / "frontend" / "src" / "ui" / "api" / "system.ts").read_text(encoding="utf-8")

    assert "getSystemDataSafetyStatus" in system_api
    assert "dataSafetyStatus.state === \"blocked\"" in projects_page
    assert "数据安全检查未通过" in projects_page


def test_admin_page_surfaces_operator_data_safety_summary() -> None:
    admin_page = (REPO_ROOT / "frontend" / "src" / "views" / "admin" / "AdminPage.tsx").read_text(encoding="utf-8")

    assert "getSystemDataSafetyStatus" in admin_page
    assert "数据安全状态" in admin_page
