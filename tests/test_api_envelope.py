from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
    get_membership_marketing_store,
    get_membership_payment_service,
    get_membership_store,
)
from adapter.errors import register_exception_handlers
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


def test_unknown_api_path_returns_error_envelope() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/not-found")
    assert resp.status_code == 404
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "NOT_FOUND",
            "message": "Not found",
        },
    }


def test_unknown_exception_hides_internal_details_by_default() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> dict:
        raise RuntimeError("sensitive-path: C:/secret/file.txt")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {
        "ok": False,
        "error": {
            "code": "UNKNOWN",
            "message": "Internal server error",
        },
    }


def test_system_capabilities_reflect_hosted_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/system/capabilities")

    assert resp.status_code == 200
    assert resp.json() == {
        "ok": True,
        "data": {
            "appMode": "hosted",
            "asrEnabled": False,
            "serverMediaStreamEnabled": False,
            "browserLocalMediaEnabled": True,
            "authEnabled": True,
            "allowSignup": True,
            "ready": True,
            "sqlBackend": "sqlite",
        },
    }


def test_hosted_mode_disables_api_docs_by_default(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    assert client.get("/api/openapi.json").status_code == 404
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/redoc").status_code == 404


def test_hosted_mode_can_enable_api_docs_explicitly(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_API_DOCS", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    openapi = client.get("/api/openapi.json")
    docs = client.get("/api/docs")
    redoc = client.get("/api/redoc")

    assert openapi.status_code == 200
    assert openapi.json()["openapi"].startswith("3.")
    assert docs.status_code == 200
    assert "Swagger UI" in docs.text
    assert redoc.status_code == 200
    assert "ReDoc" in redoc.text


def test_health_endpoint_reports_runtime_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    resp = client.get("/api/health")

    body = resp.json()
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"]
    assert body["ok"] is True
    assert body["data"]["sqlBackend"] == "sqlite"
    assert body["data"]["store"]["ok"] is True
    assert body["data"]["auth"]["ok"] is True


def test_system_runtime_requires_auth_when_auth_enabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    anon_client = TestClient(create_app())
    anon_resp = anon_client.get("/api/system/runtime")
    assert anon_resp.status_code == 401
    assert anon_resp.json()["error"]["message"] == "Authentication required"

    auth_client = TestClient(create_app())
    register_resp = auth_client.post("/api/auth/register", json={"email": "runtime-auth@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    authed_resp = auth_client.get("/api/system/runtime")
    assert authed_resp.status_code == 200
    assert authed_resp.json()["ok"] is True


def test_hosted_mode_blocks_asr_and_server_media_routes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    register_resp = client.post(
        "/api/auth/register",
        json={"email": "tester@example.com", "password": "password123"},
    )
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Hosted Feature Flags"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    asr_resp = client.post(
        f"/api/projects/{project_id}/asr",
        json={
            "recallPointId": "rp1",
            "centerMs": 1000,
            "preMs": 30000,
            "postMs": 30000,
        },
    )
    media_resp = client.get(f"/api/projects/{project_id}/media/instances/i1")

    assert asr_resp.status_code == 400
    assert asr_resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "ASR is disabled in this deployment",
        },
    }
    assert media_resp.status_code == 400
    assert media_resp.json() == {
        "ok": False,
        "error": {
            "code": "PRECONDITION",
            "message": "Server-side media streaming is disabled in this deployment",
        },
    }
    _reset_caches()
