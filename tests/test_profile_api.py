from __future__ import annotations

from pathlib import Path

import pytest
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


DEFAULT_POMODORO_MICRO_BREAKS = {
    "enabled": False,
    "minIntervalSeconds": 180,
    "maxIntervalSeconds": 300,
    "durationSeconds": 10,
}


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_rate_limit_store.cache_clear()
    get_auth_store.cache_clear()
    get_membership_commission_store.cache_clear()
    get_membership_marketing_store.cache_clear()
    get_membership_payment_service.cache_clear()
    get_membership_store.cache_clear()


def _default_pomodoro_weekly_schedule() -> dict:
    return {day: {"plans": []} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}


def _activate_membership(client: TestClient) -> None:
    created = client.post("/api/membership/orders", json={"provider": "manual_test"})
    assert created.status_code == 200
    order_id = str(created.json()["data"]["order"]["orderId"])
    confirmed = client.post(
        "/api/payments/membership/callback/manual_test",
        json={"orderId": order_id, "providerTradeNo": f"manual_{order_id}"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["membership"]["isActive"] is True


@pytest.fixture()
def auth_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_ENABLE_MANUAL_TEST_PAYMENT", "true")
    monkeypatch.setenv("PLM_BOOTSTRAP_SUPER_ADMIN_EMAILS", "owner@example.com,stranger@example.com")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_MEMBERSHIP_DB_PATH", str(tmp_path / "plm_membership.sqlite3"))
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


def test_profile_study_metrics_sync_merges_ranges(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})

    created = client.post("/api/projects", json={"title": "Metrics Project"})
    assert created.status_code == 200
    project_id = created.json()["data"]["projectId"]

    first_sync = client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-08",
            "dateTo": "2026-04-08",
            "entries": [
                {
                    "projectId": project_id,
                    "dateKey": "2026-04-08",
                    "effectiveMs": 30000,
                    "watchMs": 30000,
                    "composeMs": 0,
                    "reviewMs": 0,
                    "qaMs": 0,
                    "effectiveRanges": [{"startMs": 0, "endMs": 30000}],
                    "watchRanges": [{"startMs": 0, "endMs": 30000}],
                    "composeRanges": [],
                    "reviewRanges": [],
                    "qaRanges": [],
                }
            ],
        },
    )
    assert first_sync.status_code == 200
    first_entry = first_sync.json()["data"][0]
    assert first_entry["effectiveMs"] == 30000
    assert first_entry["watchMs"] == 30000

    second_sync = client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-08",
            "dateTo": "2026-04-08",
            "entries": [
                {
                    "projectId": project_id,
                    "dateKey": "2026-04-08",
                    "effectiveMs": 45000,
                    "watchMs": 30000,
                    "composeMs": 15000,
                    "reviewMs": 0,
                    "qaMs": 0,
                    "effectiveRanges": [{"startMs": 20000, "endMs": 45000}],
                    "watchRanges": [{"startMs": 20000, "endMs": 30000}],
                    "composeRanges": [{"startMs": 30000, "endMs": 45000}],
                    "reviewRanges": [],
                    "qaRanges": [],
                }
            ],
        },
    )
    assert second_sync.status_code == 200
    second_entry = second_sync.json()["data"][0]
    assert second_entry["effectiveMs"] == 45000
    assert second_entry["watchMs"] == 30000
    assert second_entry["composeMs"] == 15000
    assert second_entry["effectiveRanges"] == [{"startMs": 0, "endMs": 45000}]
    assert second_entry["watchRanges"] == [{"startMs": 0, "endMs": 30000}]
    assert second_entry["composeRanges"] == [{"startMs": 30000, "endMs": 45000}]

    fetched = client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-08",
            "dateTo": "2026-04-08",
            "entries": [],
        },
    )
    assert fetched.status_code == 200
    assert fetched.json()["data"][0]["effectiveMs"] == 45000


def test_profile_study_metrics_sync_supports_web_presence_partition(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})

    created = client.post("/api/projects", json={"title": "Web Metrics Project"})
    assert created.status_code == 200
    project_id = created.json()["data"]["projectId"]

    synced = client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-09",
            "dateTo": "2026-04-09",
            "entries": [
                {
                    "projectId": project_id,
                    "dateKey": "2026-04-09",
                    "schemaVersion": 2,
                    "webPresenceMs": 60_000,
                    "videoMs": 20_000,
                    "recallEntryMs": 15_000,
                    "reviewMs": 10_000,
                    "aiQaMs": 5_000,
                    "distractionMs": 10_000,
                    "presenceRanges": [{"startMs": 0, "endMs": 60_000}],
                    "videoRanges": [{"startMs": 0, "endMs": 20_000}],
                    "recallEntryRanges": [{"startMs": 20_000, "endMs": 35_000}],
                    "reviewRanges": [{"startMs": 35_000, "endMs": 45_000}],
                    "aiQaRanges": [{"startMs": 45_000, "endMs": 50_000}],
                    "isPartitionComplete": True,
                }
            ],
        },
    )

    assert synced.status_code == 200
    entry = synced.json()["data"][0]
    assert entry["schemaVersion"] == 2
    assert entry["webPresenceMs"] == 60_000
    assert entry["videoMs"] == 20_000
    assert entry["recallEntryMs"] == 15_000
    assert entry["reviewMs"] == 10_000
    assert entry["aiQaMs"] == 5_000
    assert entry["distractionMs"] == 10_000
    assert entry["presenceRanges"] == [{"startMs": 0, "endMs": 60_000}]
    assert entry["isPartitionComplete"] is True


def test_profile_study_metrics_legacy_records_are_partition_incomplete(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})

    created = client.post("/api/projects", json={"title": "Legacy Metrics Project"})
    assert created.status_code == 200
    project_id = created.json()["data"]["projectId"]

    synced = client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-10",
            "dateTo": "2026-04-10",
            "entries": [
                {
                    "projectId": project_id,
                    "dateKey": "2026-04-10",
                    "effectiveMs": 30_000,
                    "watchMs": 30_000,
                    "composeMs": 0,
                    "reviewMs": 0,
                    "qaMs": 0,
                    "effectiveRanges": [{"startMs": 0, "endMs": 30_000}],
                    "watchRanges": [{"startMs": 0, "endMs": 30_000}],
                    "composeRanges": [],
                    "reviewRanges": [],
                    "qaRanges": [],
                }
            ],
        },
    )

    assert synced.status_code == 200
    entry = synced.json()["data"][0]
    assert entry["effectiveMs"] == 30_000
    assert entry["webPresenceMs"] == 0
    assert entry["presenceRanges"] == []
    assert entry["isPartitionComplete"] is False


def test_profile_study_metrics_sync_rejects_unowned_project(auth_env: None) -> None:
    owner_client = TestClient(create_app())
    owner_client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    created = owner_client.post("/api/projects", json={"title": "Owner Project"})
    assert created.status_code == 200
    project_id = created.json()["data"]["projectId"]

    stranger_client = TestClient(create_app())
    stranger_client.post("/api/auth/register", json={"email": "stranger@example.com", "password": "password123"})
    denied = stranger_client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": "2026-04-08",
            "dateTo": "2026-04-08",
            "entries": [],
        },
    )
    assert denied.status_code == 403


def test_profile_service_settings_persist_across_relogin(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200
    _activate_membership(client)

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


def test_profile_global_settings_persist_across_relogin(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200

    default_schedule = _default_pomodoro_weekly_schedule()
    updated_schedule = {
        "mon": {
            "plans": [
                {
                    "id": "mon-morning",
                    "enabled": True,
                    "startTime": "08:30",
                    "focusMinutes": 40,
                    "breakMinutes": 8,
                    "pomodoroCount": 3,
                    "projectIds": ["project-a", "project-b", None],
                },
                {
                    "id": "mon-evening",
                    "enabled": True,
                    "startTime": "20:00",
                    "focusMinutes": 30,
                    "breakMinutes": 10,
                    "pomodoroCount": 2,
                    "projectIds": ["project-c", None],
                },
            ]
        },
        "tue": {
            "plans": [
                {
                    "id": "tue-morning",
                    "enabled": True,
                    "startTime": "08:30",
                    "focusMinutes": 40,
                    "breakMinutes": 8,
                    "pomodoroCount": 3,
                    "projectIds": ["project-a", "project-b", "project-c"],
                }
            ]
        },
        "wed": {
            "plans": [
                {
                    "id": "wed-morning",
                    "enabled": True,
                    "startTime": "08:30",
                    "focusMinutes": 40,
                    "breakMinutes": 8,
                    "pomodoroCount": 3,
                    "projectIds": [None, None, None],
                }
            ]
        },
        "thu": {
            "plans": [
                {
                    "id": "thu-morning",
                    "enabled": True,
                    "startTime": "08:30",
                    "focusMinutes": 40,
                    "breakMinutes": 8,
                    "pomodoroCount": 3,
                    "projectIds": ["project-d", None, None],
                }
            ]
        },
        "fri": {
            "plans": [
                {
                    "id": "fri-morning",
                    "enabled": True,
                    "startTime": "08:30",
                    "focusMinutes": 40,
                    "breakMinutes": 8,
                    "pomodoroCount": 3,
                    "projectIds": ["project-d", "project-e", "project-f"],
                }
            ]
        },
        "sat": {"plans": []},
        "sun": {"plans": []},
    }
    for day, payload in updated_schedule.items():
        for plan_index, plan in enumerate(payload["plans"]):
            count = int(plan["pomodoroCount"])
            plan["breakPrompt"] = f"{day} plan {plan_index + 1} rest in ten seconds"
            plan["focusPrompts"] = [f"{day} plan {plan_index + 1} focus {index + 1}" for index in range(count)]

    before = client.get("/api/profile/me/global-settings")
    assert before.status_code == 200
    assert before.json()["data"]["theme"] == "mist"
    assert before.json()["data"]["pomodoro"] == {
        "enabled": False,
        "transitionSoundEnabled": False,
        "defaultFocusPrompt": "",
        "defaultBreakPrompt": "",
        "microBreaks": DEFAULT_POMODORO_MICRO_BREAKS,
        "weeklySchedule": default_schedule,
    }
    assert before.json()["data"]["defaultProjectReviewTemplate"] == [{"kind": "CONVERGENCE"}]

    updated = client.put(
        "/api/profile/me/global-settings",
        json={
            "theme": "paper",
            "pomodoro": {
                "enabled": True,
                "transitionSoundEnabled": True,
                "defaultFocusPrompt": "十秒后开始学习，请准备专注。",
                "defaultBreakPrompt": "十秒后进入休息，请放松一下。",
                "microBreaks": {
                    "enabled": True,
                    "minIntervalSeconds": 120,
                    "maxIntervalSeconds": 240,
                    "durationSeconds": 15,
                },
                "weeklySchedule": updated_schedule,
            },
            "defaultProjectReviewTemplate": [{"kind": "REVIEW_TASK", "count": 2}],
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()["data"]
    assert updated_body["theme"] == "paper"
    assert updated_body["pomodoro"] == {
        "enabled": True,
        "transitionSoundEnabled": True,
        "defaultFocusPrompt": "十秒后开始学习，请准备专注。",
        "defaultBreakPrompt": "十秒后进入休息，请放松一下。",
        "microBreaks": {
            "enabled": True,
            "minIntervalSeconds": 120,
            "maxIntervalSeconds": 240,
            "durationSeconds": 15,
        },
        "weeklySchedule": updated_schedule,
    }
    assert updated_body["defaultProjectReviewTemplate"] == [
        {"kind": "CONVERGENCE"},
        {"kind": "REVIEW_TASK", "count": 2},
    ]
    assert updated_body["updatedAt"]

    client.post("/api/auth/logout")
    relogin = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert relogin.status_code == 200

    after = client.get("/api/profile/me/global-settings")
    assert after.status_code == 200
    after_body = after.json()["data"]
    assert after_body["theme"] == "paper"
    assert after_body["pomodoro"] == {
        "enabled": True,
        "transitionSoundEnabled": True,
        "defaultFocusPrompt": "十秒后开始学习，请准备专注。",
        "defaultBreakPrompt": "十秒后进入休息，请放松一下。",
        "microBreaks": {
            "enabled": True,
            "minIntervalSeconds": 120,
            "maxIntervalSeconds": 240,
            "durationSeconds": 15,
        },
        "weeklySchedule": updated_schedule,
    }
    assert after_body["defaultProjectReviewTemplate"] == [
        {"kind": "CONVERGENCE"},
        {"kind": "REVIEW_TASK", "count": 2},
    ]


def test_profile_global_settings_reject_overlapping_pomodoro_plans(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200

    weekly_schedule = {day: {"plans": []} for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    weekly_schedule["mon"] = {
        "plans": [
            {
                "id": "early",
                "enabled": True,
                "startTime": "09:00",
                "focusMinutes": 25,
                "breakMinutes": 5,
                "pomodoroCount": 2,
                "projectIds": [None, None],
                "breakPrompt": "",
                "focusPrompts": ["", ""],
            },
            {
                "id": "overlap",
                "enabled": True,
                "startTime": "09:30",
                "focusMinutes": 25,
                "breakMinutes": 5,
                "pomodoroCount": 1,
                "projectIds": [None],
                "breakPrompt": "",
                "focusPrompts": [""],
            },
        ]
    }

    response = client.put(
        "/api/profile/me/global-settings",
        json={
            "theme": "mist",
            "pomodoro": {
                "enabled": True,
                "transitionSoundEnabled": False,
                "weeklySchedule": weekly_schedule,
            },
            "defaultProjectReviewTemplate": [{"kind": "CONVERGENCE"}],
        },
    )

    assert response.status_code == 400
    assert "overlap" in response.json()["error"]["message"]


def test_profile_global_settings_pomodoro_micro_break_defaults_and_persistence(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200

    default_schedule = _default_pomodoro_weekly_schedule()
    before = client.get("/api/profile/me/global-settings")
    assert before.status_code == 200
    assert before.json()["data"]["pomodoro"]["microBreaks"] == DEFAULT_POMODORO_MICRO_BREAKS

    micro_breaks = {
        "enabled": True,
        "minIntervalSeconds": 90,
        "maxIntervalSeconds": 210,
        "durationSeconds": 20,
    }
    updated = client.put(
        "/api/profile/me/global-settings",
        json={
            "theme": "mist",
            "pomodoro": {
                "enabled": True,
                "transitionSoundEnabled": False,
                "defaultFocusPrompt": "",
                "defaultBreakPrompt": "",
                "microBreaks": micro_breaks,
                "weeklySchedule": default_schedule,
            },
            "defaultProjectReviewTemplate": [{"kind": "CONVERGENCE"}],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["pomodoro"]["microBreaks"] == micro_breaks

    client.post("/api/auth/logout")
    relogin = client.post("/api/auth/login", json={"email": "owner@example.com", "password": "password123"})
    assert relogin.status_code == 200

    after = client.get("/api/profile/me/global-settings")
    assert after.status_code == 200
    assert after.json()["data"]["pomodoro"]["microBreaks"] == micro_breaks


def test_profile_global_settings_rejects_invalid_pomodoro_micro_break_ordering(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})

    response = client.put(
        "/api/profile/me/global-settings",
        json={
            "theme": "mist",
            "pomodoro": {
                "enabled": True,
                "transitionSoundEnabled": False,
                "defaultFocusPrompt": "",
                "defaultBreakPrompt": "",
                "microBreaks": {
                    "enabled": True,
                    "minIntervalSeconds": 300,
                    "maxIntervalSeconds": 120,
                    "durationSeconds": 20,
                },
                "weeklySchedule": _default_pomodoro_weekly_schedule(),
            },
            "defaultProjectReviewTemplate": [{"kind": "CONVERGENCE"}],
        },
    )

    assert response.status_code == 400


def test_profile_global_settings_rejects_invalid_pomodoro_micro_break_bounds(auth_env: None) -> None:
    client = TestClient(create_app())
    client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})

    response = client.put(
        "/api/profile/me/global-settings",
        json={
            "theme": "mist",
            "pomodoro": {
                "enabled": True,
                "transitionSoundEnabled": False,
                "defaultFocusPrompt": "",
                "defaultBreakPrompt": "",
                "microBreaks": {
                    "enabled": True,
                    "minIntervalSeconds": 10,
                    "maxIntervalSeconds": 3601,
                    "durationSeconds": 4,
                },
                "weeklySchedule": _default_pomodoro_weekly_schedule(),
            },
            "defaultProjectReviewTemplate": [{"kind": "CONVERGENCE"}],
        },
    )

    assert response.status_code == 400


def test_profile_learning_plans_sync_and_survive_global_settings_update(auth_env: None) -> None:
    client = TestClient(create_app())
    registered = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert registered.status_code == 200

    empty = client.get("/api/profile/me/learning-plans")
    assert empty.status_code == 200
    assert empty.json()["data"] == {"plans": [], "progressSnapshots": []}

    learning_plans = {
        "plans": [
            {
                "planId": "plan:calculus:one",
                "projectId": "calculus",
                "title": "两周冲完极限",
                "targetKind": "LEARNING_OBJECT_NODES",
                "learningObjectNodeIds": ["node-a", "node-b"],
                "targetDays": 14,
                "createdDateKey": "2026-04-10",
                "dueDateKey": "2026-04-23",
                "archivedAt": None,
                "updatedAt": 1775779200000,
            }
        ],
        "progressSnapshots": [
            {
                "planId": "plan:calculus:one",
                "dateKey": "2026-04-10",
                "progressRatio": 0.25,
                "updatedAt": 1775779200001,
            }
        ],
    }
    synced = client.put("/api/profile/me/learning-plans", json=learning_plans)
    assert synced.status_code == 200
    assert synced.json()["data"] == learning_plans
    assert client.get("/api/profile/me/global-settings").json()["data"]["learningPlans"] == learning_plans

    settings = client.get("/api/profile/me/global-settings").json()["data"]
    updated_settings = client.put(
        "/api/profile/me/global-settings",
        json={
            "theme": "paper",
            "pomodoro": settings["pomodoro"],
            "defaultProjectReviewTemplate": settings["defaultProjectReviewTemplate"],
        },
    )
    assert updated_settings.status_code == 200
    assert updated_settings.json()["data"]["learningPlans"] == learning_plans
    assert client.get("/api/profile/me/learning-plans").json()["data"] == learning_plans


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
    _activate_membership(client)

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


def test_system_pomodoro_tts_preview_returns_audio_when_auth_enabled(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapter.routers import system as system_router

    async def fake_synthesize_pomodoro_prompt_audio(text: str) -> bytes:
        assert text == "十秒后开始学习"
        return b"fake-mp3"

    monkeypatch.setattr(
        system_router,
        "synthesize_pomodoro_prompt_audio",
        fake_synthesize_pomodoro_prompt_audio,
    )

    client = TestClient(create_app())
    register = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register.status_code == 200
    _activate_membership(client)
    response = client.post("/api/system/pomodoro/tts-preview", json={"text": "十秒后开始学习"})

    assert response.status_code == 200
    assert response.content == b"fake-mp3"
    assert response.headers["content-type"].startswith("audio/mpeg")


def test_system_pomodoro_tts_preview_returns_unavailable_for_tts_failure(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adapter.routers import system as system_router
    from backend.system.pomodoro_tts import PomodoroTtsUnavailable

    async def fake_synthesize_pomodoro_prompt_audio(text: str) -> bytes:
        raise PomodoroTtsUnavailable("pomodoro TTS service is unavailable")

    monkeypatch.setattr(
        system_router,
        "synthesize_pomodoro_prompt_audio",
        fake_synthesize_pomodoro_prompt_audio,
    )

    client = TestClient(create_app())
    register = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register.status_code == 200
    _activate_membership(client)
    response = client.post("/api/system/pomodoro/tts-preview", json={"text": "十秒后开始学习"})

    assert response.status_code == 503
    assert response.json()["error"]["message"] == "pomodoro TTS service is unavailable"
