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
    _reset_caches()
    yield
    _reset_caches()


def _register(client: TestClient, email: str) -> dict:
    response = client.post("/api/auth/register", json={"email": email, "password": "password123"})
    assert response.status_code == 200
    return response.json()["data"]


def _create_project(client: TestClient, title: str) -> str:
    response = client.post(
        "/api/projects",
        json={
            "title": title,
            "initialProjectType": "LOOSE_POINTS",
            "initialSourceKind": "MANUAL",
        },
    )
    assert response.status_code == 200
    return str(response.json()["data"]["projectId"])


def _submit_single_item_learning_task(client: TestClient, project_id: str, title: str) -> None:
    response = client.post(
        f"/api/projects/{project_id}/learning-tasks",
        json={
            "title": title,
            "items": [
                {
                    "question": [{"kind": "TEXT", "text": "Question"}],
                    "answer": [{"kind": "TEXT", "text": "Answer"}],
                }
            ],
        },
    )
    assert response.status_code == 200


def _queue_head(client: TestClient, project_id: str) -> str:
    response = client.get(f"/api/projects/{project_id}/queue")
    assert response.status_code == 200
    head_id = response.json()["data"]["headId"]
    assert head_id
    return str(head_id)


def _commit_review(client: TestClient, project_id: str, review_task_id: str, can_recall: list[int]) -> None:
    response = client.post(
        f"/api/projects/{project_id}/review-tasks/{review_task_id}/commit",
        json={"canRecall": can_recall},
    )
    assert response.status_code == 200


def _sync_study_metrics(
    client: TestClient,
    project_id: str,
    *,
    date_key: str,
    effective_ms: int,
    watch_ms: int,
    compose_ms: int,
    review_ms: int,
    qa_ms: int,
    effective_ranges: list[dict[str, int]],
    watch_ranges: list[dict[str, int]],
    compose_ranges: list[dict[str, int]],
    review_ranges: list[dict[str, int]],
    qa_ranges: list[dict[str, int]],
) -> None:
    response = client.post(
        "/api/profile/me/study-metrics/sync",
        json={
            "projectIds": [project_id],
            "dateFrom": date_key,
            "dateTo": date_key,
            "entries": [
                {
                    "projectId": project_id,
                    "dateKey": date_key,
                    "effectiveMs": effective_ms,
                    "watchMs": watch_ms,
                    "composeMs": compose_ms,
                    "reviewMs": review_ms,
                    "qaMs": qa_ms,
                    "effectiveRanges": effective_ranges,
                    "watchRanges": watch_ranges,
                    "composeRanges": compose_ranges,
                    "reviewRanges": review_ranges,
                    "qaRanges": qa_ranges,
                }
            ],
        },
    )
    assert response.status_code == 200


def test_friend_request_accept_list_and_delete_flow(auth_env: None) -> None:
    app = create_app()
    alice_client = TestClient(app)
    bob_client = TestClient(app)

    alice = _register(alice_client, "alice@example.com")
    bob = _register(bob_client, "bob@example.com")

    created = alice_client.post(
        "/api/friends/requests",
        json={"publicUid": bob["publicUid"], "message": "一起学习呀"},
    )
    assert created.status_code == 200
    assert created.json()["data"]["status"] == "pending"
    assert created.json()["data"]["user"]["publicUid"] == bob["publicUid"]
    request_id = created.json()["data"]["requestId"]

    incoming = bob_client.get("/api/friends/requests?box=incoming")
    assert incoming.status_code == 200
    assert incoming.json()["data"][0]["requestId"] == request_id
    assert incoming.json()["data"][0]["user"]["publicUid"] == alice["publicUid"]

    accepted = bob_client.post(f"/api/friends/requests/{request_id}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["data"]["status"] == "accepted"

    alice_friends = alice_client.get("/api/friends")
    assert alice_friends.status_code == 200
    assert alice_friends.json()["data"][0]["userId"] == bob["userId"]

    bob_friends = bob_client.get("/api/friends")
    assert bob_friends.status_code == 200
    assert bob_friends.json()["data"][0]["userId"] == alice["userId"]

    deleted = alice_client.delete(f"/api/friends/{bob['userId']}")
    assert deleted.status_code == 200

    assert alice_client.get("/api/friends").json()["data"] == []
    assert bob_client.get("/api/friends").json()["data"] == []


def test_friend_request_blocks_self_and_duplicate_pending_requests(auth_env: None) -> None:
    app = create_app()
    alice_client = TestClient(app)
    bob_client = TestClient(app)

    alice = _register(alice_client, "self-alice@example.com")
    bob = _register(bob_client, "self-bob@example.com")

    self_request = alice_client.post("/api/friends/requests", json={"publicUid": alice["publicUid"], "message": "加我自己"})
    assert self_request.status_code == 400
    assert self_request.json()["error"]["message"] == "cannot send a friend request to yourself"

    first = alice_client.post("/api/friends/requests", json={"publicUid": bob["publicUid"], "message": "先发一个"})
    assert first.status_code == 200

    duplicate = alice_client.post("/api/friends/requests", json={"publicUid": bob["publicUid"], "message": "再发一个"})
    assert duplicate.status_code == 400
    assert duplicate.json()["error"]["message"] == "friend request already pending"


def test_reverse_pending_friend_request_auto_accepts(auth_env: None) -> None:
    app = create_app()
    alice_client = TestClient(app)
    bob_client = TestClient(app)

    alice = _register(alice_client, "reverse-alice@example.com")
    bob = _register(bob_client, "reverse-bob@example.com")

    first = alice_client.post("/api/friends/requests", json={"publicUid": bob["publicUid"], "message": "来做好友"})
    assert first.status_code == 200
    request_id = first.json()["data"]["requestId"]

    auto_accept = bob_client.post("/api/friends/requests", json={"publicUid": alice["publicUid"], "message": "我也想加你"})
    assert auto_accept.status_code == 200
    assert auto_accept.json()["data"]["status"] == "accepted"
    assert auto_accept.json()["data"]["requestId"] == request_id

    alice_outgoing = alice_client.get("/api/friends/requests?box=outgoing")
    assert alice_outgoing.status_code == 200
    assert alice_outgoing.json()["data"][0]["status"] == "accepted"

    assert len(alice_client.get("/api/friends").json()["data"]) == 1
    assert len(bob_client.get("/api/friends").json()["data"]) == 1


def test_requester_can_cancel_pending_friend_request(auth_env: None) -> None:
    app = create_app()
    alice_client = TestClient(app)
    bob_client = TestClient(app)

    alice = _register(alice_client, "cancel-alice@example.com")
    bob = _register(bob_client, "cancel-bob@example.com")

    created = alice_client.post("/api/friends/requests", json={"publicUid": bob["publicUid"], "message": "先发申请"})
    assert created.status_code == 200
    request_id = created.json()["data"]["requestId"]

    cancelled = alice_client.post(f"/api/friends/requests/{request_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"

    incoming = bob_client.get("/api/friends/requests?box=incoming")
    assert incoming.status_code == 200
    assert incoming.json()["data"][0]["status"] == "cancelled"
    assert bob_client.get("/api/friends").json()["data"] == []


def test_only_receiver_can_accept_friend_request(auth_env: None) -> None:
    app = create_app()
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    charlie_client = TestClient(app)

    alice = _register(alice_client, "permission-alice@example.com")
    bob = _register(bob_client, "permission-bob@example.com")
    _register(charlie_client, "permission-charlie@example.com")

    created = alice_client.post("/api/friends/requests", json={"publicUid": bob["publicUid"], "message": "权限测试"})
    assert created.status_code == 200
    request_id = created.json()["data"]["requestId"]

    sender_accept = alice_client.post(f"/api/friends/requests/{request_id}/accept")
    assert sender_accept.status_code == 400
    assert sender_accept.json()["error"]["message"] == "only the receiver can accept this friend request"

    outsider_reject = charlie_client.post(f"/api/friends/requests/{request_id}/reject")
    assert outsider_reject.status_code == 400
    assert outsider_reject.json()["error"]["message"] == "only the receiver can reject this friend request"


def test_friend_profile_and_leaderboard_include_learning_stats(auth_env: None) -> None:
    app = create_app()
    alice_client = TestClient(app)
    bob_client = TestClient(app)
    charlie_client = TestClient(app)

    alice = _register(alice_client, "stats-alice@example.com")
    bob = _register(bob_client, "stats-bob@example.com")
    _register(charlie_client, "stats-charlie@example.com")

    created = alice_client.post(
        "/api/friends/requests",
        json={"publicUid": bob["publicUid"], "message": "一起卷学习统计"},
    )
    assert created.status_code == 200
    request_id = created.json()["data"]["requestId"]

    accepted = bob_client.post(f"/api/friends/requests/{request_id}/accept")
    assert accepted.status_code == 200

    alice_project_id = _create_project(alice_client, "Alice Stats Project")
    _submit_single_item_learning_task(alice_client, alice_project_id, "Alice Task")
    _commit_review(alice_client, alice_project_id, _queue_head(alice_client, alice_project_id), [1])
    _sync_study_metrics(
        alice_client,
        alice_project_id,
        date_key="2026-04-09",
        effective_ms=45_000,
        watch_ms=20_000,
        compose_ms=15_000,
        review_ms=10_000,
        qa_ms=0,
        effective_ranges=[{"startMs": 0, "endMs": 45_000}],
        watch_ranges=[{"startMs": 0, "endMs": 20_000}],
        compose_ranges=[{"startMs": 20_000, "endMs": 35_000}],
        review_ranges=[{"startMs": 35_000, "endMs": 45_000}],
        qa_ranges=[],
    )

    bob_project_id = _create_project(bob_client, "Bob Stats Project")
    _submit_single_item_learning_task(bob_client, bob_project_id, "Bob Task")
    _commit_review(bob_client, bob_project_id, _queue_head(bob_client, bob_project_id), [1])
    _submit_single_item_learning_task(bob_client, bob_project_id, "Bob Task 2")
    _sync_study_metrics(
        bob_client,
        bob_project_id,
        date_key="2026-04-09",
        effective_ms=30_000,
        watch_ms=18_000,
        compose_ms=12_000,
        review_ms=0,
        qa_ms=0,
        effective_ranges=[{"startMs": 0, "endMs": 30_000}],
        watch_ranges=[{"startMs": 0, "endMs": 18_000}],
        compose_ranges=[{"startMs": 18_000, "endMs": 30_000}],
        review_ranges=[],
        qa_ranges=[],
    )

    friend_profile = alice_client.get(f"/api/friends/{bob['userId']}/profile")
    assert friend_profile.status_code == 200
    friend_profile_data = friend_profile.json()["data"]
    assert friend_profile_data["userId"] == bob["userId"]
    assert friend_profile_data["publicUid"] == bob["publicUid"]
    assert friend_profile_data["stats"]["projectCount"] == 1
    assert friend_profile_data["stats"]["effectiveMs"] == 30_000
    assert friend_profile_data["stats"]["watchMs"] == 18_000
    assert friend_profile_data["stats"]["composeMs"] == 12_000
    assert friend_profile_data["stats"]["reviewMs"] == 0
    assert friend_profile_data["stats"]["qaMs"] == 0
    assert friend_profile_data["stats"]["learningCount"] == 2
    assert friend_profile_data["stats"]["reviewCount"] == 1
    assert friend_profile_data["stats"]["totalActions"] == 3
    assert friend_profile_data["stats"]["studyDays"] == 1
    assert friend_profile_data["stats"]["lastStudyAt"] is not None

    leaderboard = alice_client.get("/api/friends/leaderboard")
    assert leaderboard.status_code == 200
    leaderboard_data = leaderboard.json()["data"]
    assert leaderboard_data[0]["user"]["userId"] == alice["userId"]
    assert leaderboard_data[0]["isSelf"] is True
    assert leaderboard_data[0]["stats"]["effectiveMs"] == 45_000
    assert leaderboard_data[0]["stats"]["learningCount"] == 1
    assert leaderboard_data[0]["stats"]["reviewCount"] == 1
    assert leaderboard_data[0]["stats"]["totalActions"] == 2

    bob_entry = next(item for item in leaderboard_data if item["user"]["userId"] == bob["userId"])
    assert bob_entry["isSelf"] is False
    assert bob_entry["friendedAt"] is not None
    assert bob_entry["stats"]["effectiveMs"] == 30_000
    assert bob_entry["stats"]["learningCount"] == 2
    assert bob_entry["stats"]["reviewCount"] == 1
    assert bob_entry["stats"]["totalActions"] == 3

    denied = charlie_client.get(f"/api/friends/{bob['userId']}/profile")
    assert denied.status_code == 404
    assert denied.json()["error"]["message"] == "Friend not found"
