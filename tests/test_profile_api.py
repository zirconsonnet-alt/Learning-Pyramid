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
