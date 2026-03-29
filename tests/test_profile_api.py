from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
    get_membership_marketing_store,
    get_membership_payment_service,
    get_membership_store,
)
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


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
    monkeypatch.setenv("PLM_DATA_DIR", str(tmp_path / "runtime-data"))
    _reset_caches()
    yield
    _reset_caches()


def test_profile_round_trip_and_password_change(auth_env: None) -> None:
    client = TestClient(create_app())

    register = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register.status_code == 200
    public_uid = register.json()["data"]["publicUid"]
    assert public_uid.startswith("LP")

    profile = client.get("/api/profile/me")
    assert profile.status_code == 200
    assert profile.json()["data"]["nickname"] == "owner"
    assert profile.json()["data"]["bio"] == ""

    updated = client.patch("/api/profile/me", json={"nickname": "Owner Name", "bio": "Learning builder"})
    assert updated.status_code == 200
    assert updated.json()["data"]["nickname"] == "Owner Name"
    assert updated.json()["data"]["bio"] == "Learning builder"

    found = client.get(f"/api/users/by-uid/{public_uid}")
    assert found.status_code == 200
    assert found.json()["data"]["nickname"] == "Owner Name"
    assert "email" not in found.json()["data"]

    changed = client.post(
        "/api/profile/me/password",
        json={"currentPassword": "password123", "newPassword": "password456"},
    )
    assert changed.status_code == 200

    client.post("/api/auth/logout")
    denied = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert denied.status_code == 401

    relogin = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password456"})
    assert relogin.status_code == 200


def test_profile_avatar_upload(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})

    png_bytes = (
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        b"\x00\x00\x00\x0cIDAT\x08\x99c``\x00\x00\x00\x04\x00\x01\xf6\x178U"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    uploaded = client.put("/api/profile/me/avatar", content=png_bytes, headers={"Content-Type": "image/png"})
    assert uploaded.status_code == 200
    avatar_url = uploaded.json()["data"]["avatarUrl"]
    assert avatar_url

    avatar = client.get(avatar_url)
    assert avatar.status_code == 200
    assert avatar.headers["content-type"].startswith("image/png")


def test_profile_service_settings_persist_across_relogin(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200

    llm_before = client.get("/api/profile/me/llm-settings")
    assert llm_before.status_code == 200
    assert llm_before.json()["data"]["llmSource"] == "none"
    assert llm_before.json()["data"]["promptAssemblyMode"] == "system"

    llm_updated = client.put(
        "/api/profile/me/llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-user-12345678",
            "promptAssemblyMode": "user_concat",
        },
    )
    assert llm_updated.status_code == 200
    assert llm_updated.json()["data"]["llmConfigured"] is True
    assert llm_updated.json()["data"]["llmSource"] == "user"
    assert llm_updated.json()["data"]["promptAssemblyMode"] == "user_concat"
    assert llm_updated.json()["data"]["savedApiKeyConfigured"] is True
    assert llm_updated.json()["data"]["savedApiKeyPreview"] == "sk-u...5678"

    capabilities = client.get("/api/system/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["data"]["llmConfigured"] is True
    assert capabilities.json()["data"]["llmSource"] == "user"

    asr_updated = client.put(
        "/api/profile/me/asr-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "whisper-1",
            "apiKey": "sk-asr-abcdefgh1234",
        },
    )
    assert asr_updated.status_code == 200
    assert asr_updated.json()["data"]["asrConfigured"] is True
    assert asr_updated.json()["data"]["asrSource"] == "user"
    assert asr_updated.json()["data"]["savedApiKeyConfigured"] is True
    assert asr_updated.json()["data"]["savedApiKeyPreview"] == "sk-a...1234"

    client.post("/api/auth/logout")
    relogin = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert relogin.status_code == 200

    llm_after = client.get("/api/profile/me/llm-settings")
    assert llm_after.status_code == 200
    assert llm_after.json()["data"]["baseUrl"] == "https://api.openai.com/v1"
    assert llm_after.json()["data"]["modelName"] == "gpt-4o-mini"
    assert llm_after.json()["data"]["promptAssemblyMode"] == "user_concat"
    assert llm_after.json()["data"]["savedApiKeyConfigured"] is True
    assert llm_after.json()["data"]["savedApiKeyPreview"] == "sk-u...5678"

    asr_after = client.get("/api/profile/me/asr-settings")
    assert asr_after.status_code == 200
    assert asr_after.json()["data"]["baseUrl"] == "https://api.openai.com/v1"
    assert asr_after.json()["data"]["modelName"] == "whisper-1"
    assert asr_after.json()["data"]["savedApiKeyConfigured"] is True
    assert asr_after.json()["data"]["savedApiKeyPreview"] == "sk-a...1234"


def test_auth_mode_does_not_fallback_to_deployment_llm_settings(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_NATIVE_LLM_QA_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("PLM_NATIVE_LLM_QA_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("PLM_NATIVE_LLM_QA_API_KEY", "sk-env-12345678")

    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200

    llm_before = client.get("/api/profile/me/llm-settings")
    assert llm_before.status_code == 200
    assert llm_before.json()["data"]["baseUrl"] == ""
    assert llm_before.json()["data"]["modelName"] == ""
    assert llm_before.json()["data"]["llmConfigured"] is False
    assert llm_before.json()["data"]["storyGenerationConfigured"] is False
    assert llm_before.json()["data"]["llmSource"] == "none"
    assert llm_before.json()["data"]["promptAssemblyMode"] == "system"

    capabilities = client.get("/api/system/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["data"]["llmConfigured"] is False
    assert capabilities.json()["data"]["storyGenerationConfigured"] is False
    assert capabilities.json()["data"]["llmSource"] == "none"


def test_auth_mode_disables_global_llm_settings_endpoint(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200
    assert registered.json()["data"]["roles"] == ["super_admin"]

    listed = client.get("/api/system/global-llm-settings")
    assert listed.status_code == 400
    assert listed.json()["error"]["message"] == "Global LLM settings are disabled when auth is enabled"

    updated = client.put(
        "/api/system/global-llm-settings",
        json={
            "baseUrl": "https://api.openai.com/v1",
            "modelName": "gpt-4o-mini",
            "apiKey": "sk-global-12345678",
        },
    )
    assert updated.status_code == 400
    assert updated.json()["error"]["message"] == "Global LLM settings are disabled when auth is enabled"
