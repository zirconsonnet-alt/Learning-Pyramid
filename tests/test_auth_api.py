from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapter.deps import get_api, get_auth_store
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_store.cache_clear()


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()
    yield
    _reset_caches()


def test_auth_required_and_project_owner_sees_created_project(auth_env: None) -> None:
    client = TestClient(create_app())

    unauthorized = client.get("/api/projects")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {
        "ok": False,
        "error": {
            "code": "UNAUTHORIZED",
            "message": "Authentication required",
        },
    }

    register = client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert register.status_code == 200
    assert register.json()["data"]["email"] == "owner@example.com"

    initial_projects = client.get("/api/projects")
    assert initial_projects.status_code == 200
    assert initial_projects.json() == {"ok": True, "data": []}

    create_project = client.post("/api/projects", json={"title": "Hosted Project"})
    assert create_project.status_code == 200
    project_id = create_project.json()["data"]["projectId"]

    projects = client.get("/api/projects")
    assert projects.status_code == 200
    items = projects.json()["data"]
    assert len(items) == 1
    assert items[0]["projectId"] == project_id
    assert items[0]["title"] == "Hosted Project"
    assert items[0]["state"] == "ACTIVE"
    assert items[0]["deletedAt"] is None


def test_project_access_is_isolated_between_users(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    stranger_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Private Project"})
    project_id = created.json()["data"]["projectId"]

    stranger_client.post(
        "/api/auth/register",
        json={"email": "stranger@example.com", "password": "password123"},
    )

    projects = stranger_client.get("/api/projects")
    assert projects.status_code == 200
    assert projects.json() == {"ok": True, "data": []}

    forbidden = stranger_client.get(f"/api/projects/{project_id}/project-config")
    assert forbidden.status_code == 403
    assert forbidden.json() == {
        "ok": False,
        "error": {
            "code": "FORBIDDEN",
            "message": "Project access denied",
        },
    }


def test_project_material_source_binding_can_be_read_and_updated(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    initial = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert initial.status_code == 200
    initial_data = initial.json()["data"]
    assert initial_data["projectId"] == project_id
    assert initial_data["sourceKind"] == "SERVER_FS"
    assert initial_data["sourceRootLabel"] is None
    assert isinstance(initial_data["updatedAt"], str)

    updated = client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "SERVER_FS",
            "sourceRootLabel": "Course Videos",
        },
    )
    assert updated.status_code == 200
    assert updated.json() == {"ok": True, "data": None}

    fetched = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert fetched.status_code == 200
    fetched_data = fetched.json()["data"]
    assert fetched_data["projectId"] == project_id
    assert fetched_data["sourceKind"] == "SERVER_FS"
    assert fetched_data["sourceRootLabel"] == "Course Videos"
    assert isinstance(fetched_data["updatedAt"], str)
    assert fetched_data["updatedAt"] >= initial_data["updatedAt"]

    audit_events = client.get(f"/api/projects/{project_id}/audit-log-events")
    assert audit_events.status_code == 200
    assert audit_events.json()["data"][-1]["apiName"] == "set_project_material_source_binding"
