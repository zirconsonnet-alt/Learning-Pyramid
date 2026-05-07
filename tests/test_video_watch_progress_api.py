from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from adapter.deps import (
    get_api,
    get_auth_rate_limit_store,
    get_auth_store,
    get_membership_commission_store,
    get_membership_marketing_store,
    get_membership_payment_service,
    get_membership_store,
)
from adapter.main import create_app


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_commission_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


def test_video_watch_progress_persists_project_instance_completion(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "local")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    client = TestClient(create_app())
    project_id = client.post(
        "/api/projects",
        json={"title": "课程", "initialSourceKind": "MANUAL", "initialProjectType": "COURSE"},
    ).json()["data"]["projectId"]
    instance_id = client.post(
        f"/api/projects/{project_id}/instances",
        json={"materialId": "chapter-01.mp4"},
    ).json()["data"]["instanceId"]

    range_resp = client.post(
        f"/api/projects/{project_id}/instances/{instance_id}/video-watch-progress/ranges",
        json={"startMs": 0, "endMs": 60_000, "durationMs": 120_000},
    )
    assert range_resp.status_code == 200
    assert range_resp.json()["data"]["watchedMs"] == 60_000
    assert range_resp.json()["data"]["completedAt"] is None

    complete_resp = client.post(
        f"/api/projects/{project_id}/instances/{instance_id}/video-watch-progress/completed",
        json={"durationMs": 120_000},
    )
    assert complete_resp.status_code == 200
    completed = complete_resp.json()["data"]
    assert completed["durationMs"] == 120_000
    assert completed["watchedMs"] == 120_000
    assert completed["ranges"] == [{"startMs": 0, "endMs": 120_000}]
    assert completed["completedAt"]

    _reset_caches()
    restarted_client = TestClient(create_app())
    progress_resp = restarted_client.get(
        f"/api/projects/{project_id}/video-watch-progress",
        params={"instanceIds": instance_id},
    )
    assert progress_resp.status_code == 200
    assert progress_resp.json()["data"][instance_id]["watchedMs"] == 120_000
