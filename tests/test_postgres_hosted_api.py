from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapter.deps import get_api, get_auth_store, get_membership_marketing_store, get_membership_payment_service, get_membership_store
from adapter.main import create_app
from backend.system.api import SystemAPI
from backend.system.auth_store import SQLiteAuthStore
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore
from tests.postgres_test_support import require_postgres_test_dsn, reset_postgres_database
from tools.backup_runtime_bundle import backup_runtime_bundle
from tools.migrate_sqlite_to_postgres import migrate_sqlite_to_postgres
from tools.restore_runtime_bundle import restore_runtime_bundle


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


@pytest.fixture()
def hosted_postgres_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    dsn = require_postgres_test_dsn()
    reset_postgres_database(dsn)
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_SQL_BACKEND", "postgres")
    monkeypatch.setenv("PLM_POSTGRES_DSN", dsn)
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_ENABLE_BROWSER_LOCAL_MEDIA", "true")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.delenv("PLM_STORE_DB_PATH", raising=False)
    monkeypatch.delenv("PLM_AUTH_DB_PATH", raising=False)
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path / "runtime-data"))
    _reset_caches()
    yield dsn
    _reset_caches()


def test_postgres_hosted_app_project_lifecycle_and_runtime_health(hosted_postgres_env: str) -> None:
    client = TestClient(create_app())

    unauthorized = client.get("/api/projects")
    assert unauthorized.status_code == 401
    assert unauthorized.headers["X-Request-ID"]

    health = client.get("/api/health")
    runtime = client.get("/api/system/runtime")
    assert health.status_code == 200
    assert runtime.status_code == 200
    assert health.json()["data"]["sqlBackend"] == "postgres"
    assert health.json()["data"]["store"]["ok"] is True
    assert health.json()["data"]["auth"]["ok"] is True
    assert runtime.json()["data"]["store"]["pool"]["maxPoolSize"] >= 1

    register = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register.status_code == 200

    logout = client.post("/api/auth/logout")
    assert logout.status_code == 200

    denied_after_logout = client.get("/api/projects")
    assert denied_after_logout.status_code == 401

    login = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert login.status_code == 200

    created = client.post("/api/projects", json={"title": "Hosted PG Project"})
    assert created.status_code == 200
    project_id = created.json()["data"]["projectId"]

    listed = client.get("/api/projects")
    assert listed.status_code == 200
    assert [item["projectId"] for item in listed.json()["data"]] == [project_id]

    project_config = client.get(f"/api/projects/{project_id}/project-config")
    assert project_config.status_code == 200
    assert project_config.json()["data"]["projectId"] == project_id

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 200

    final_list = client.get("/api/projects")
    assert final_list.status_code == 200
    assert final_list.json() == {"ok": True, "data": []}


def test_postgres_hosted_app_migration_backup_and_restore_round_trip(hosted_postgres_env: str, tmp_path: Path) -> None:
    store_db = tmp_path / "legacy-store.sqlite3"
    auth_db = tmp_path / "legacy-auth.sqlite3"
    project_root = tmp_path / "project-migrated-api"

    sqlite_api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_db)))
    project_id = sqlite_api.create_project("Migrated Via API", project_root=str(project_root))
    sqlite_auth = SQLiteAuthStore(auth_db)
    user = sqlite_auth.create_user("migrate@example.com", "password123")
    sqlite_auth.add_project_owner(str(project_id), user.user_id)

    migrate_sqlite_to_postgres(store_db=store_db, auth_db=auth_db, postgres_dsn=hosted_postgres_env)
    _reset_caches()

    client = TestClient(create_app())
    login = client.post("/api/auth/login", json={"email": "migrate@example.com", "password": "password123"})
    assert login.status_code == 200

    projects = client.get("/api/projects")
    assert projects.status_code == 200
    assert [item["projectId"] for item in projects.json()["data"]] == [str(project_id)]

    bundle_path = tmp_path / "runtime-backup.json"
    backup_runtime_bundle(output_path=bundle_path)
    assert bundle_path.exists()

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 200
    assert client.get("/api/projects").json() == {"ok": True, "data": []}

    restore_runtime_bundle(input_path=bundle_path)
    _reset_caches()
    restored_client = TestClient(create_app())
    restored_login = restored_client.post("/api/auth/login", json={"email": "migrate@example.com", "password": "password123"})
    assert restored_login.status_code == 200
    restored_projects = restored_client.get("/api/projects")
    assert restored_projects.status_code == 200
    assert [item["projectId"] for item in restored_projects.json()["data"]] == [str(project_id)]
