from __future__ import annotations

from pathlib import Path
from threading import Thread
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from adapter.deps import get_api, get_auth_store, get_desktop_agent_runtime
from adapter.main import create_app
from backend.models.desktop_media_probe_cache import DesktopMediaProbeCache
from backend.models.hls_cache_entry import HlsCacheEntry
from backend.models.enums import DesktopAgentStatus
from backend.system.desktop_agent_setup_code import decode_desktop_agent_setup_code


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_store.cache_clear()
    get_desktop_agent_runtime.cache_clear()


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


def _seed_progressive_probe_cache(project_id: str, instance_id: str, agent_id: str) -> None:
    get_auth_store().upsert_desktop_media_probe_cache(
        DesktopMediaProbeCache(
            project_id=project_id,
            instance_id=instance_id,
            agent_id=agent_id,
            container="mp4",
            video_codec="h264",
            audio_codec="aac",
            duration_ms=60_000,
            bitrate_bps=1_500_000,
            width=1280,
            height=720,
            updated_at="2026-03-11T12:00:00+00:00",
        )
    )


def _seed_hls_probe_cache(project_id: str, instance_id: str, agent_id: str) -> None:
    get_auth_store().upsert_desktop_media_probe_cache(
        DesktopMediaProbeCache(
            project_id=project_id,
            instance_id=instance_id,
            agent_id=agent_id,
            container="mkv",
            video_codec="hevc",
            audio_codec="aac",
            duration_ms=60_000,
            bitrate_bps=6_000_000,
            width=1920,
            height=1080,
            updated_at="2026-03-11T12:00:00+00:00",
        )
    )


def _respond_probe_request(
    websocket,
    *,
    container: str,
    video_codec: str | None,
    audio_codec: str | None,
    bitrate_bps: int | None,
    relative_path: str,
    fps: float | None = None,
    audio_channels: int | None = None,
    audio_sample_rate: int | None = None,
    video_stream_count: int | None = None,
    audio_stream_count: int | None = None,
    subtitle_stream_count: int | None = None,
    size_bytes: int | None = None,
    modified_at: str | None = None,
) -> dict:
    command = websocket.receive_json()
    assert command["type"] == "probe.request"
    assert command["relativePath"] == relative_path
    websocket.send_json(
        {
            "type": "probe.result",
            "requestId": command["requestId"],
            "projectId": command["projectId"],
            "instanceId": command["instanceId"],
            "relativePath": command["relativePath"],
            "container": container,
            "videoCodec": video_codec,
            "audioCodec": audio_codec,
            "durationMs": 60_000,
            "bitrateBps": bitrate_bps,
            "width": 1280,
            "height": 720,
            "fps": fps,
            "audioChannels": audio_channels,
            "audioSampleRate": audio_sample_rate,
            "videoStreamCount": video_stream_count,
            "audioStreamCount": audio_stream_count,
            "subtitleStreamCount": subtitle_stream_count,
            "sizeBytes": size_bytes,
            "modifiedAt": modified_at,
        }
    )
    return command


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
    assert initial_data["desktopAgentId"] is None
    assert initial_data["sourceRootLabel"] is None
    assert isinstance(initial_data["updatedAt"], str)

    pairing = client.post("/api/desktop-agents/pairing-codes")
    assert pairing.status_code == 200
    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert paired.status_code == 200
    agent_id = paired.json()["data"]["agentId"]

    updated = client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": agent_id,
            "sourceRootLabel": "Videos",
        },
    )
    assert updated.status_code == 200
    assert updated.json() == {"ok": True, "data": None}

    fetched = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert fetched.status_code == 200
    fetched_data = fetched.json()["data"]
    assert fetched_data["projectId"] == project_id
    assert fetched_data["sourceKind"] == "DESKTOP_AGENT_MANIFEST"
    assert fetched_data["desktopAgentId"] == agent_id
    assert fetched_data["sourceRootLabel"] == "Videos"
    assert isinstance(fetched_data["updatedAt"], str)
    assert fetched_data["updatedAt"] >= initial_data["updatedAt"]

    audit_events = client.get(f"/api/projects/{project_id}/audit-log-events")
    assert audit_events.status_code == 200
    assert audit_events.json()["data"][-1]["apiName"] == "set_project_material_source_binding"


def test_desktop_agent_pairing_flow_and_binding_validation(auth_env: None) -> None:
    owner_client = TestClient(create_app())
    stranger_client = TestClient(create_app())

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    assert pairing.status_code == 200
    pairing_code = pairing.json()["data"]["pairingCode"]
    assert isinstance(pairing.json()["data"]["expiresAt"], str)

    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_code,
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert paired.status_code == 200
    pair_data = paired.json()["data"]
    assert pair_data["agentId"].startswith("agent_")
    assert pair_data["agentToken"]
    assert pair_data["refreshToken"]
    assert isinstance(pair_data["serverTime"], str)

    agents = owner_client.get("/api/desktop-agents")
    assert agents.status_code == 200
    assert [item["agentId"] for item in agents.json()["data"]] == [pair_data["agentId"]]

    bind = owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    assert bind.status_code == 200

    stranger_client.post(
        "/api/auth/register",
        json={"email": "stranger@example.com", "password": "password123"},
    )
    forbidden = stranger_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    assert forbidden.status_code == 403


def test_desktop_agent_refresh_token_rotates_agent_credentials(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = client.post("/api/desktop-agents/pairing-codes")
    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )

    refreshed = client.post(
        "/api/desktop-agents/refresh-token",
        json={"refreshToken": pair_data["refreshToken"]},
    )
    assert refreshed.status_code == 200
    refresh_data = refreshed.json()["data"]
    assert refresh_data["agentId"] == pair_data["agentId"]
    assert refresh_data["agentToken"] != pair_data["agentToken"]
    assert refresh_data["refreshToken"] != pair_data["refreshToken"]
    assert get_auth_store().get_desktop_agent_by_token(refresh_data["agentToken"]).agent_id == pair_data["agentId"]

    stale_refresh = client.post(
        "/api/desktop-agents/refresh-token",
        json={"refreshToken": pair_data["refreshToken"]},
    )
    assert stale_refresh.status_code == 401
    assert stale_refresh.json()["error"]["message"] == "Invalid desktop agent refresh token"

    stale_manifest_sync = client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    assert stale_manifest_sync.status_code == 401
    assert stale_manifest_sync.json()["error"]["message"] == "Invalid agent token"

    manifest_sync = client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {refresh_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    assert manifest_sync.status_code == 200
    assert manifest_sync.json()["data"]["created_instances_count"] == 1


def test_desktop_agent_manifest_sync_updates_project_materials(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = client.post("/api/desktop-agents/pairing-codes")
    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]

    bind = client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    assert bind.status_code == 200

    sync = client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [
                {
                    "relativePath": "course-1/lesson-01.mp4",
                    "displayName": "Lesson 01",
                    "mediaKind": "video",
                    "sizeBytes": 1234,
                    "modifiedAt": "2026-03-11T12:00:00+00:00",
                },
                {
                    "relativePath": "course-1/lesson-02.mp4",
                    "displayName": "Lesson 02",
                    "mediaKind": "video",
                    "sizeBytes": 5678,
                    "modifiedAt": "2026-03-11T12:05:00+00:00",
                },
            ],
        },
    )
    assert sync.status_code == 200
    assert sync.json()["data"]["created_instances_count"] == 2

    instances = client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    assert sorted(item["materialId"] for item in instances.json()["data"]) == [
        "course-1/lesson-01.mp4",
        "course-1/lesson-02.mp4",
    ]

    nodes = client.get(f"/api/projects/{project_id}/learning-object-nodes")
    assert nodes.status_code == 200
    assert len(nodes.json()["data"]) == 4
    leaf_titles = sorted(item["title"] for item in nodes.json()["data"] if item["kind"] == "leaf")
    assert leaf_titles == ["Lesson 01", "Lesson 02"]


def test_desktop_agent_setup_session_bootstrap_and_finalize_binding(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "ML"})
    project_id = created.json()["data"]["projectId"]

    sync_manifest = client.post(
        f"/api/projects/{project_id}/media-manifest/sync",
        json={
            "rootTitle": "videos",
            "entries": [
                {
                    "relativePath": "videos/lesson-01.mp4",
                    "displayName": "Lesson 01",
                    "mediaKind": "video",
                }
            ],
        },
    )
    assert sync_manifest.status_code == 200

    create_session = client.post(
        "/api/system/desktop-agent/setup-sessions",
        json={"preferredProjectId": project_id},
    )
    assert create_session.status_code == 200
    setup_session = create_session.json()["data"]
    assert setup_session["preferredProjectId"] == project_id
    setup_code = setup_session["setupCode"]
    decoded = decode_desktop_agent_setup_code(setup_code)
    assert decoded.server_url.endswith("testserver")

    bootstrap = client.get("/api/desktop-agents/setup-bootstrap", params={"setupCode": setup_code})
    assert bootstrap.status_code == 200
    bootstrap_data = bootstrap.json()["data"]
    assert bootstrap_data["preferredProjectId"] == project_id
    assert bootstrap_data["pairingCode"]
    project = next(item for item in bootstrap_data["projects"] if item["projectId"] == project_id)
    candidate_roots = {item["rootKey"]: item for item in project["candidateRoots"]}
    assert "." in candidate_roots
    assert candidate_roots["."]["relativePath"] == ""
    assert candidate_roots["."]["sourceRootLabel"] is None
    assert "videos" in candidate_roots
    assert candidate_roots["videos"]["relativePath"] == "videos"
    assert candidate_roots["videos"]["sourceRootLabel"] == "videos"

    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": bootstrap_data["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0-beta.1",
        },
    )
    assert paired.status_code == 200
    agent_id = paired.json()["data"]["agentId"]

    finalized = client.post(
        "/api/desktop-agents/setup-complete",
        json={
            "setupCode": setup_code,
            "agentId": agent_id,
            "projectId": project_id,
            "sourceRootLabel": "videos",
        },
    )
    assert finalized.status_code == 200
    assert finalized.json()["data"] == {
        "projectId": project_id,
        "agentId": agent_id,
        "sourceRootLabel": "videos",
    }

    binding = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert binding.status_code == 200
    assert binding.json()["data"]["sourceKind"] == "DESKTOP_AGENT_MANIFEST"
    assert binding.json()["data"]["desktopAgentId"] == agent_id
    assert binding.json()["data"]["sourceRootLabel"] == "videos"


def test_desktop_agent_account_login_bootstrap_pair_and_finalize_binding(auth_env: None) -> None:
    client = TestClient(create_app())

    register = client.post(
        "/api/auth/register",
        json={"email": "account-agent@example.com", "password": "password123"},
    )
    assert register.status_code == 200
    created = client.post("/api/projects", json={"title": "ML"})
    assert created.status_code == 200
    project_id = created.json()["data"]["projectId"]

    sync_manifest = client.post(
        f"/api/projects/{project_id}/media-manifest/sync",
        json={
            "rootTitle": "videos",
            "entries": [
                {
                    "relativePath": "videos/lesson-01.mp4",
                    "displayName": "Lesson 01",
                    "mediaKind": "video",
                }
            ],
        },
    )
    assert sync_manifest.status_code == 200

    bootstrap = client.get("/api/desktop-agents/account-bootstrap")
    assert bootstrap.status_code == 200
    bootstrap_data = bootstrap.json()["data"]
    assert bootstrap_data["serverUrl"].endswith("testserver")
    project = next(item for item in bootstrap_data["projects"] if item["projectId"] == project_id)
    candidate_roots = {item["rootKey"]: item for item in project["candidateRoots"]}
    assert "." in candidate_roots
    assert "videos" in candidate_roots
    assert candidate_roots["videos"]["sourceRootLabel"] == "videos"

    paired = client.post(
        "/api/desktop-agents/account-pair",
        json={
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0-beta.1",
        },
    )
    assert paired.status_code == 200
    agent_id = paired.json()["data"]["agentId"]

    finalized = client.post(
        "/api/desktop-agents/account-complete",
        json={
            "agentId": agent_id,
            "projectId": project_id,
            "sourceRootLabel": "videos",
        },
    )
    assert finalized.status_code == 200
    assert finalized.json()["data"] == {
        "projectId": project_id,
        "agentId": agent_id,
        "sourceRootLabel": "videos",
    }

    binding = client.get(f"/api/projects/{project_id}/material-source-binding")
    assert binding.status_code == 200
    assert binding.json()["data"]["sourceKind"] == "DESKTOP_AGENT_MANIFEST"
    assert binding.json()["data"]["desktopAgentId"] == agent_id
    assert binding.json()["data"]["sourceRootLabel"] == "videos"


def test_desktop_agent_account_pair_reuses_existing_device_agent(auth_env: None) -> None:
    client = TestClient(create_app())

    register = client.post(
        "/api/auth/register",
        json={"email": "device-reuse@example.com", "password": "password123"},
    )
    assert register.status_code == 200

    first_pair = client.post(
        "/api/desktop-agents/account-pair",
        json={
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0-beta.1",
        },
    )
    assert first_pair.status_code == 200
    first_data = first_pair.json()["data"]

    second_pair = client.post(
        "/api/desktop-agents/account-pair",
        json={
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0-beta.2",
        },
    )
    assert second_pair.status_code == 200
    second_data = second_pair.json()["data"]

    assert second_data["agentId"] == first_data["agentId"]

    agents = client.get("/api/desktop-agents")
    assert agents.status_code == 200
    assert agents.json()["data"] == [
        {
            "agentId": first_data["agentId"],
            "userId": register.json()["data"]["userId"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0-beta.2",
            "status": "OFFLINE",
            "lastSeenAt": second_data["serverTime"],
            "pairedAt": second_data["serverTime"],
        }
    ]

    stale_diagnostic = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {first_data['agentToken']}"},
        json={
            "level": "warning",
            "category": "service",
            "eventType": "stale_agent",
            "message": "should fail",
            "details": {},
        },
    )
    assert stale_diagnostic.status_code == 401

    current_diagnostic = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {second_data['agentToken']}"},
        json={
            "level": "warning",
            "category": "service",
            "eventType": "current_agent",
            "message": "works",
            "details": {},
        },
    )
    assert current_diagnostic.status_code == 200


def test_desktop_agent_manifest_sync_invalidates_stale_probe_and_hls_cache(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PLM_AGENT_CACHE_DIR", str(tmp_path / "desktop-cache"))
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = client.post("/api/desktop-agents/pairing-codes")
    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    sync = client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [
                {
                    "relativePath": "course-1/lesson-01.mp4",
                    "displayName": "Lesson 01",
                    "mediaKind": "video",
                    "sizeBytes": 1234,
                    "modifiedAt": "2026-03-11T12:00:00+00:00",
                }
            ],
        },
    )
    assert sync.status_code == 200
    instance_id = client.get(f"/api/projects/{project_id}/instances").json()["data"][0]["instanceId"]

    get_auth_store().upsert_desktop_media_probe_cache(
        DesktopMediaProbeCache(
            project_id=project_id,
            instance_id=instance_id,
            agent_id=pair_data["agentId"],
            container="mp4",
            video_codec="h264",
            audio_codec="aac",
            duration_ms=60_000,
            bitrate_bps=1_500_000,
            width=1280,
            height=720,
            size_bytes=1234,
            modified_at="2026-03-11T12:00:00+00:00",
            updated_at="2026-03-11T12:00:01+00:00",
        )
    )
    from backend.system.desktop_media_hls import resolve_hls_artifact_disk_path

    artifact_path = resolve_hls_artifact_disk_path("cache_manifest_stale", "master.m3u8")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("#EXTM3U\n", encoding="utf-8")
    get_auth_store().upsert_hls_cache_entry(
        HlsCacheEntry(
            cache_key="cache_manifest_stale",
            project_id=project_id,
            instance_id=instance_id,
            agent_id=pair_data["agentId"],
            profile='{"heightMax":720}',
            segment_name="master.m3u8",
            file_path=str(artifact_path),
            size_bytes=len(artifact_path.read_bytes()),
            created_at="2026-03-11T12:00:00+00:00",
            last_accessed_at="2026-03-11T12:00:00+00:00",
            expires_at="2026-03-12T12:00:00+00:00",
        )
    )
    runtime = get_desktop_agent_runtime()
    job, _ = runtime.create_or_get_hls_job(
        cache_key="cache_manifest_stale",
        agent_id=pair_data["agentId"],
        project_id=project_id,
        instance_id=instance_id,
        relative_path="course-1/lesson-01.mp4",
        profile={"heightMax": 720},
    )

    refreshed_sync = client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [
                {
                    "relativePath": "course-1/lesson-01.mp4",
                    "displayName": "Lesson 01",
                    "mediaKind": "video",
                    "sizeBytes": 4321,
                    "modifiedAt": "2026-03-11T12:30:00+00:00",
                }
            ],
        },
    )

    assert refreshed_sync.status_code == 200
    assert get_auth_store().get_desktop_media_probe_cache(project_id, instance_id, pair_data["agentId"]) is None
    assert get_auth_store().list_hls_cache_entries("cache_manifest_stale") == ()
    assert not artifact_path.exists()
    assert runtime.get_hls_job(job.job_id).state == "CANCELLED"
    assert runtime.get_hls_job(job.job_id).message == "desktop agent media changed during manifest sync"


def test_desktop_agent_manifest_sync_rejects_unbound_agent(auth_env: None) -> None:
    owner_client = TestClient(create_app())
    other_client = TestClient(create_app())

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    owner_pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    owner_paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": owner_pairing.json()["data"]["pairingCode"],
            "deviceName": "OWNER-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    owner_agent = owner_paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": owner_agent["agentId"],
            "sourceRootLabel": "Videos",
        },
    )

    other_client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "password": "password123"},
    )
    other_pairing = other_client.post("/api/desktop-agents/pairing-codes")
    other_paired = other_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": other_pairing.json()["data"]["pairingCode"],
            "deviceName": "OTHER-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    other_agent = other_paired.json()["data"]

    denied = other_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {other_agent['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": other_agent["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    assert denied.status_code == 403


def test_desktop_agent_websocket_updates_online_status(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = client.post("/api/desktop-agents/pairing-codes")
    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )

    with client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        connected = websocket.receive_json()
        assert connected == {"type": "connected", "agentId": pair_data["agentId"]}

        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.1",
            }
        )
        hello_ack = websocket.receive_json()
        assert hello_ack["type"] == "hello.ack"

        websocket.send_json({"type": "heartbeat", "at": "2026-03-11T12:00:00+00:00"})
        heartbeat_ack = websocket.receive_json()
        assert heartbeat_ack["type"] == "heartbeat.ack"

        status = client.get(f"/api/projects/{project_id}/desktop-agents/status")
        assert status.status_code == 200
        status_data = status.json()["data"]
        assert status_data["binding"]["desktopAgentId"] == pair_data["agentId"]
        assert status_data["agent"]["status"] == "ONLINE"
        assert status_data["agent"]["connected"] is True
        assert status_data["agent"]["connectionState"] == "CONNECTED"
        assert status_data["agent"]["appVersion"] == "0.1.1"
        assert isinstance(status_data["agent"]["lastSeenAt"], str)
        assert status_data["agent"]["lastSeenAt"] == heartbeat_ack["serverTime"]

    after_disconnect = client.get(f"/api/projects/{project_id}/desktop-agents/status")
    assert after_disconnect.status_code == 200
    assert after_disconnect.json()["data"]["agent"]["status"] == "ONLINE"
    assert after_disconnect.json()["data"]["agent"]["connected"] is False
    assert after_disconnect.json()["data"]["agent"]["connectionState"] == "RECONNECTING"


def test_project_desktop_agent_status_turns_offline_after_presence_grace(auth_env: None) -> None:
    client = TestClient(create_app())

    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = client.post("/api/desktop-agents/pairing-codes")
    paired = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )

    get_auth_store().update_desktop_agent_presence(
        pair_data["agentId"],
        status=DesktopAgentStatus.ONLINE,
        last_seen_at="2026-03-11T12:00:00+00:00",
    )

    status = client.get(f"/api/projects/{project_id}/desktop-agents/status")
    assert status.status_code == 200
    status_data = status.json()["data"]["agent"]
    assert status_data["status"] == "OFFLINE"
    assert status_data["connected"] is False
    assert status_data["connectionState"] == "OFFLINE"


def test_desktop_agent_playback_descriptor_returns_hls_for_incompatible_probe(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mkv"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor_holder: dict[str, object] = {}

        def _fetch_descriptor() -> None:
            descriptor_holder["response"] = owner_client.get(
                f"/api/projects/{project_id}/media/instances/{instance_id}/playback"
            )

        descriptor_worker = Thread(target=_fetch_descriptor)
        descriptor_worker.start()
        _respond_probe_request(
            websocket,
            container="mkv",
            video_codec="hevc",
            audio_codec="aac",
            bitrate_bps=6_000_000,
            relative_path="course-1/lesson-01.mkv",
            fps=23.976,
            audio_channels=2,
            audio_sample_rate=48_000,
            video_stream_count=1,
            audio_stream_count=1,
            subtitle_stream_count=1,
            size_bytes=9_999_999,
            modified_at="2026-03-11T12:10:00+00:00",
        )
        descriptor_worker.join(timeout=5)

        descriptor = descriptor_holder["response"]
        assert getattr(descriptor, "status_code") == 200
        descriptor_data = descriptor.json()["data"]
        assert descriptor_data["mode"] == "relay_hls"
        assert descriptor_data["ready"] is False
        assert descriptor_data["supportsRange"] is False
        assert descriptor_data["reason"] == "transcode_pending"
        assert descriptor_data["decisionReason"] == "container:mkv"
        assert descriptor_data["probe"]["container"] == "mkv"
        assert descriptor_data["probe"]["videoCodec"] == "hevc"
        assert descriptor_data["probe"]["audioCodec"] == "aac"
        assert descriptor_data["probe"]["fps"] == 23.976
        assert descriptor_data["probe"]["subtitleStreamCount"] == 1
        assert descriptor_data["probe"]["sizeBytes"] == 9_999_999
        assert descriptor_data["probe"]["modifiedAt"] == "2026-03-11T12:10:00+00:00"
        cached_probe = get_auth_store().get_desktop_media_probe_cache(project_id, instance_id, pair_data["agentId"])
        assert cached_probe is not None
        assert cached_probe.container == "mkv"
        assert cached_probe.video_codec == "hevc"
        assert cached_probe.fps == 23.976
        assert cached_probe.audio_channels == 2
        assert cached_probe.audio_sample_rate == 48_000
        assert cached_probe.subtitle_stream_count == 1
        assert cached_probe.size_bytes == 9_999_999
        assert cached_probe.modified_at == "2026-03-11T12:10:00+00:00"
        hls_command = websocket.receive_json()
        assert hls_command["type"] == "hls.start"
        assert hls_command["relativePath"] == "course-1/lesson-01.mkv"
        assert hls_command["jobId"]

        cached_lookup_started_at = time.monotonic()
        cached_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert time.monotonic() - cached_lookup_started_at < 0.5
        assert cached_descriptor.status_code == 200
        assert cached_descriptor.json()["data"]["mode"] == "relay_hls"
        runtime_snapshot = get_desktop_agent_runtime().snapshot_state()
        assert runtime_snapshot["hlsCacheRequestCount"] == 2
        assert runtime_snapshot["hlsCacheHitCount"] == 0
        assert runtime_snapshot["hlsCacheMissCount"] == 2


def test_desktop_agent_playback_descriptor_uses_browser_capability_matrix_for_hevc_mp4(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor_holder: dict[str, object] = {}

        def _fetch_descriptor() -> None:
            descriptor_holder["response"] = owner_client.get(
                f"/api/projects/{project_id}/media/instances/{instance_id}/playback",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )

        descriptor_worker = Thread(target=_fetch_descriptor)
        descriptor_worker.start()
        _respond_probe_request(
            websocket,
            container="mp4",
            video_codec="hevc",
            audio_codec="aac",
            bitrate_bps=2_000_000,
            relative_path="course-1/lesson-01.mp4",
            fps=24.0,
            audio_channels=2,
            audio_sample_rate=48_000,
            video_stream_count=1,
            audio_stream_count=1,
            subtitle_stream_count=0,
            size_bytes=1_234_567,
            modified_at="2026-03-11T12:20:00+00:00",
        )
        descriptor_worker.join(timeout=5)

        descriptor = descriptor_holder["response"]
        assert getattr(descriptor, "status_code") == 200
        descriptor_data = descriptor.json()["data"]
        assert descriptor_data["mode"] == "relay_hls"
        assert descriptor_data["decisionReason"] == "browser:chromium/video_codec:hevc"
        hls_command = websocket.receive_json()
        assert hls_command["type"] == "hls.start"

        safari_descriptor = owner_client.get(
            f"/api/projects/{project_id}/media/instances/{instance_id}/playback",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
                )
            },
        )
        assert safari_descriptor.status_code == 200
        safari_data = safari_descriptor.json()["data"]
        assert safari_data["mode"] == "relay_progressive"
        assert safari_data["decisionReason"] == "progressive_supported"

        baidu_android_descriptor = owner_client.get(
            f"/api/projects/{project_id}/media/instances/{instance_id}/playback",
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Linux; U; Android 13; zh-cn; V2148A Build/TQ3A.230805.001) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Mobile Safari/537.36 "
                    "baidubrowser/13.52.0.10"
                )
            },
        )
        assert baidu_android_descriptor.status_code == 200
        baidu_android_data = baidu_android_descriptor.json()["data"]
        assert baidu_android_data["mode"] == "relay_hls"
        assert baidu_android_data["decisionReason"] == "video_codec:hevc"


def test_desktop_agent_playback_descriptor_can_force_hls_for_progressive_supported_probe(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor_holder: dict[str, object] = {}

        def _fetch_descriptor() -> None:
            descriptor_holder["response"] = owner_client.get(
                f"/api/projects/{project_id}/media/instances/{instance_id}/playback?preferHls=1",
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )

        descriptor_worker = Thread(target=_fetch_descriptor)
        descriptor_worker.start()
        _respond_probe_request(
            websocket,
            container="mp4",
            video_codec="h264",
            audio_codec="aac",
            bitrate_bps=2_000_000,
            relative_path="course-1/lesson-01.mp4",
            fps=24.0,
            audio_channels=2,
            audio_sample_rate=48_000,
            video_stream_count=1,
            audio_stream_count=1,
            subtitle_stream_count=0,
            size_bytes=1_234_567,
            modified_at="2026-03-11T12:20:00+00:00",
        )
        descriptor_worker.join(timeout=5)

        descriptor = descriptor_holder["response"]
        assert getattr(descriptor, "status_code") == 200
        descriptor_data = descriptor.json()["data"]
        assert descriptor_data["mode"] == "relay_hls"
        assert descriptor_data["decisionReason"] == "prefer_hls:progressive_supported"
        hls_command = websocket.receive_json()
        assert hls_command["type"] == "hls.start"


def test_desktop_agent_playback_descriptor_preserves_failed_hls_reason_without_requeue(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mkv"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_hls_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        first_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert first_descriptor.status_code == 200
        first_data = first_descriptor.json()["data"]
        assert first_data["mode"] == "relay_hls"
        assert first_data["reason"] == "transcode_pending"

        hls_command = websocket.receive_json()
        assert hls_command["type"] == "hls.start"
        websocket.send_json({"type": "job.state", "jobId": hls_command["jobId"], "state": "FAILED", "message": "ffmpeg executable not found"})

        failed_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert failed_descriptor.status_code == 200
        failed_data = failed_descriptor.json()["data"]
        assert failed_data["mode"] == "relay_hls"
        assert failed_data["ready"] is False
        assert failed_data["reason"] == "ffmpeg executable not found"
        runtime = get_desktop_agent_runtime()
        runtime_jobs = runtime.list_hls_jobs(agent_id=pair_data["agentId"])
        assert len(runtime_jobs) == 1
        assert runtime_jobs[0].job_id == hls_command["jobId"]
        assert runtime_jobs[0].state == "FAILED"

        runtime._hls_jobs.clear()
        runtime._hls_job_ids_by_cache_key.clear()

        persisted_failed_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert persisted_failed_descriptor.status_code == 200
        persisted_failed_data = persisted_failed_descriptor.json()["data"]
        assert persisted_failed_data["mode"] == "relay_hls"
        assert persisted_failed_data["ready"] is False
        assert persisted_failed_data["reason"] == "ffmpeg executable not found"
        assert runtime.list_hls_jobs(agent_id=pair_data["agentId"]) == ()
        assert runtime.snapshot_state()["queuedCommandCount"] == 0


def test_desktop_agent_playback_descriptor_requeues_cancelled_hls_job(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mkv"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_hls_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        first_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert first_descriptor.status_code == 200
        assert first_descriptor.json()["data"]["reason"] == "transcode_pending"

        first_command = websocket.receive_json()
        assert first_command["type"] == "hls.start"
        websocket.send_json(
            {
                "type": "job.state",
                "jobId": first_command["jobId"],
                "state": "CANCELLED",
                "message": "desktop agent HLS job cancelled",
            }
        )

        retry_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert retry_descriptor.status_code == 200
        retry_data = retry_descriptor.json()["data"]
        assert retry_data["mode"] == "relay_hls"
        assert retry_data["ready"] is False
        assert retry_data["reason"] == "transcode_pending"

        second_command = websocket.receive_json()
        assert second_command["type"] == "hls.start"
        assert second_command["jobId"] != first_command["jobId"]

        runtime = get_desktop_agent_runtime()
        latest_job = runtime.get_hls_job_by_cache_key(retry_data["streamId"])
        assert latest_job is not None
        assert latest_job.job_id == second_command["jobId"]
        assert latest_job.state == "OPENING"


def test_desktop_agent_playback_descriptor_requeues_persisted_cancelled_hls_job(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mkv"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_hls_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        first_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert first_descriptor.status_code == 200
        assert first_descriptor.json()["data"]["reason"] == "transcode_pending"

        first_command = websocket.receive_json()
        assert first_command["type"] == "hls.start"
        websocket.send_json(
            {
                "type": "job.state",
                "jobId": first_command["jobId"],
                "state": "CANCELLED",
                "message": "desktop agent HLS job cancelled",
            }
        )

        runtime = get_desktop_agent_runtime()
        runtime._hls_jobs.clear()
        runtime._hls_job_ids_by_cache_key.clear()

        retry_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert retry_descriptor.status_code == 200
        retry_data = retry_descriptor.json()["data"]
        assert retry_data["mode"] == "relay_hls"
        assert retry_data["ready"] is False
        assert retry_data["reason"] == "transcode_pending"

        second_command = websocket.receive_json()
        assert second_command["type"] == "hls.start"
        assert second_command["jobId"] != first_command["jobId"]


def test_desktop_agent_hls_artifact_round_trip(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    anonymous_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mkv"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_hls_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert descriptor.status_code == 200
        descriptor_data = descriptor.json()["data"]
        assert descriptor_data["mode"] == "relay_hls"
        assert descriptor_data["ready"] is False
        stream_id = descriptor_data["streamId"]

        hls_command = websocket.receive_json()
        assert hls_command["type"] == "hls.start"
        assert hls_command["relativePath"] == "course-1/lesson-01.mkv"
        assert hls_command["jobId"]

        websocket.send_json({"type": "job.state", "jobId": hls_command["jobId"], "state": "RUNNING"})
        master_upload = agent_client.put(
            f"/api/desktop-agents/hls-jobs/{hls_command['jobId']}/artifacts/master.m3u8",
            headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
            content=b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000\nindex.m3u8\n",
        )
        assert master_upload.status_code == 200
        index_upload = agent_client.put(
            f"/api/desktop-agents/hls-jobs/{hls_command['jobId']}/artifacts/index.m3u8",
            headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
            content=b"#EXTM3U\n#EXTINF:6.0,\nsegment000.ts\n#EXT-X-ENDLIST\n",
        )
        assert index_upload.status_code == 200
        segment_upload = agent_client.put(
            f"/api/desktop-agents/hls-jobs/{hls_command['jobId']}/artifacts/segment000.ts",
            headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
            content=b"fake-ts-segment",
        )
        assert segment_upload.status_code == 200
        websocket.send_json({"type": "job.state", "jobId": hls_command["jobId"], "state": "COMPLETED"})

        ready_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert ready_descriptor.status_code == 200
        ready_data = ready_descriptor.json()["data"]
        assert ready_data["mode"] == "relay_hls"
        assert ready_data["ready"] is True
        assert ready_data["streamId"] == stream_id
        parsed_manifest_url = urlsplit(ready_data["manifestUrl"])
        assert parsed_manifest_url.path == f"/api/media/streams/{stream_id}/master.m3u8"
        assert parse_qs(parsed_manifest_url.query)["mediaAccessToken"]

        manifest = anonymous_client.get(ready_data["manifestUrl"])
        assert manifest.status_code == 200
        manifest_text = manifest.text
        manifest_paths = [line.strip() for line in manifest_text.splitlines() if line.strip() and not line.startswith("#")]
        assert len(manifest_paths) == 1
        assert manifest_paths[0].startswith("index.m3u8?mediaAccessToken=")
        playlist = anonymous_client.get(f"/api/media/streams/{stream_id}/{manifest_paths[0]}")
        assert playlist.status_code == 200
        playlist_text = playlist.text
        playlist_paths = [line.strip() for line in playlist_text.splitlines() if line.strip() and not line.startswith("#")]
        assert len(playlist_paths) == 1
        assert playlist_paths[0].startswith("segment000.ts?mediaAccessToken=")
        segment = anonymous_client.get(f"/api/media/streams/{stream_id}/{playlist_paths[0]}")
        assert segment.status_code == 200
        assert segment.content == b"fake-ts-segment"

        cached_entries = get_auth_store().list_hls_cache_entries(stream_id)
        assert [item.segment_name for item in cached_entries] == ["index.m3u8", "master.m3u8", "segment000.ts"]
        persisted_hls_jobs = get_auth_store().list_desktop_agent_hls_job_audits_for_project(project_id)
        assert len(persisted_hls_jobs) == 1
        persisted_job = persisted_hls_jobs[0]
        assert persisted_job.job_id == hls_command["jobId"]
        assert persisted_job.state == "COMPLETED"
        assert persisted_job.artifact_count == 3
        assert persisted_job.artifact_bytes == sum(
            len(payload)
            for payload in (
                b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000\nindex.m3u8\n",
                b"#EXTM3U\n#EXTINF:6.0,\nsegment000.ts\n#EXT-X-ENDLIST\n",
                b"fake-ts-segment",
            )
        )
        assert persisted_job.finished_at is not None
        runtime_snapshot = get_desktop_agent_runtime().snapshot_state()
        assert runtime_snapshot["hlsCacheRequestCount"] == 2
        assert runtime_snapshot["hlsCacheHitCount"] == 1
        assert runtime_snapshot["hlsCacheMissCount"] == 1
        assert runtime_snapshot["hlsCacheHitRate"] == 0.5
        assert runtime_snapshot["hlsArtifactRequestCount"] == 3
        assert runtime_snapshot["hlsArtifactBytesServed"] == len(manifest.content) + len(playlist.content) + len(segment.content)


def test_desktop_agent_hls_job_can_complete_over_http_after_websocket_disconnect(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mkv"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_hls_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert descriptor.status_code == 200
        descriptor_data = descriptor.json()["data"]
        assert descriptor_data["mode"] == "relay_hls"
        assert descriptor_data["ready"] is False
        assert descriptor_data["reason"] == "transcode_pending"

        hls_command = websocket.receive_json()
        assert hls_command["type"] == "hls.start"
        assert hls_command["jobId"]

        running_update = agent_client.put(
            f"/api/desktop-agents/hls-jobs/{hls_command['jobId']}/state",
            headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
            json={"state": "RUNNING"},
        )
        assert running_update.status_code == 200

    pending_after_disconnect = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
    assert pending_after_disconnect.status_code == 200
    pending_data = pending_after_disconnect.json()["data"]
    assert pending_data["mode"] == "relay_hls"
    assert pending_data["ready"] is False
    assert pending_data["reason"] == "transcode_pending"

    for artifact_path, payload in (
        ("master.m3u8", b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000\nindex.m3u8\n"),
        ("index.m3u8", b"#EXTM3U\n#EXTINF:6.0,\nsegment000.ts\n#EXT-X-ENDLIST\n"),
        ("segment000.ts", b"fake-ts-segment"),
    ):
        upload = agent_client.put(
            f"/api/desktop-agents/hls-jobs/{hls_command['jobId']}/artifacts/{artifact_path}",
            headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
            content=payload,
        )
        assert upload.status_code == 200

    completed_update = agent_client.put(
        f"/api/desktop-agents/hls-jobs/{hls_command['jobId']}/state",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={"state": "COMPLETED"},
    )
    assert completed_update.status_code == 200

    ready_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
    assert ready_descriptor.status_code == 200
    ready_data = ready_descriptor.json()["data"]
    assert ready_data["mode"] == "relay_hls"
    assert ready_data["ready"] is True

    persisted_hls_jobs = get_auth_store().list_desktop_agent_hls_job_audits_for_project(project_id)
    assert len(persisted_hls_jobs) == 1
    persisted_job = persisted_hls_jobs[0]
    assert persisted_job.job_id == hls_command["jobId"]
    assert persisted_job.state == "COMPLETED"
    assert persisted_job.artifact_count == 3
    assert persisted_job.finished_at is not None


def test_desktop_agent_playback_descriptor_probe_times_out(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_AGENT_PROBE_TIMEOUT_SECONDS", "1")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor_holder: dict[str, object] = {}

        def _fetch_descriptor() -> None:
            descriptor_holder["response"] = owner_client.get(
                f"/api/projects/{project_id}/media/instances/{instance_id}/playback"
            )

        descriptor_worker = Thread(target=_fetch_descriptor)
        descriptor_worker.start()
        probe_command = websocket.receive_json()
        assert probe_command["type"] == "probe.request"
        assert probe_command["relativePath"] == "course-1/lesson-01.mp4"
        descriptor_worker.join(timeout=5)

        descriptor = descriptor_holder["response"]
        assert getattr(descriptor, "status_code") == 504
        assert descriptor.json()["error"]["message"] == "desktop agent media probe timed out"
        assert get_auth_store().get_desktop_media_probe_cache(project_id, instance_id, pair_data["agentId"]) is None
        diagnostic_events = get_auth_store().list_all_desktop_agent_diagnostic_events()
        assert [item.event_type for item in diagnostic_events] == ["probe_timed_out"]
        assert diagnostic_events[0].category == "probe"


def test_desktop_agent_progressive_playback_relay_round_trip(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    anonymous_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor_holder: dict[str, object] = {}

        def _fetch_descriptor() -> None:
            descriptor_holder["response"] = owner_client.get(
                f"/api/projects/{project_id}/media/instances/{instance_id}/playback"
            )

        descriptor_worker = Thread(target=_fetch_descriptor)
        descriptor_worker.start()
        _respond_probe_request(
            websocket,
            container="mp4",
            video_codec="h264",
            audio_codec="aac",
            bitrate_bps=1_500_000,
            relative_path="course-1/lesson-01.mp4",
            fps=29.97,
            audio_channels=2,
            audio_sample_rate=44_100,
            video_stream_count=1,
            audio_stream_count=1,
            subtitle_stream_count=0,
            size_bytes=10,
            modified_at="2026-03-11T12:15:00+00:00",
        )
        descriptor_worker.join(timeout=5)

        descriptor = descriptor_holder["response"]
        assert getattr(descriptor, "status_code") == 200
        descriptor_data = descriptor.json()["data"]
        assert descriptor_data["mode"] == "relay_progressive"
        assert descriptor_data["supportsRange"] is True
        assert descriptor_data["decisionReason"] == "progressive_supported"
        parsed_relay_url = urlsplit(descriptor_data["url"])
        assert parsed_relay_url.path == f"/api/projects/{project_id}/media/instances/{instance_id}/relay-file"
        assert parse_qs(parsed_relay_url.query)["mediaAccessToken"]
        assert descriptor_data["probe"]["container"] == "mp4"
        assert descriptor_data["probe"]["videoCodec"] == "h264"
        assert descriptor_data["probe"]["audioCodec"] == "aac"
        assert descriptor_data["probe"]["fps"] == 29.97
        assert descriptor_data["probe"]["sizeBytes"] == 10
        assert descriptor_data["probe"]["modifiedAt"] == "2026-03-11T12:15:00+00:00"
        cached_probe = get_auth_store().get_desktop_media_probe_cache(project_id, instance_id, pair_data["agentId"])
        assert cached_probe is not None
        assert cached_probe.container == "mp4"
        assert cached_probe.video_codec == "h264"
        assert cached_probe.audio_codec == "aac"
        assert cached_probe.fps == 29.97
        assert cached_probe.audio_channels == 2
        assert cached_probe.audio_sample_rate == 44_100
        assert cached_probe.video_stream_count == 1
        assert cached_probe.audio_stream_count == 1
        assert cached_probe.subtitle_stream_count == 0
        assert cached_probe.size_bytes == 10
        assert cached_probe.modified_at == "2026-03-11T12:15:00+00:00"

        cached_lookup_started_at = time.monotonic()
        cached_descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert time.monotonic() - cached_lookup_started_at < 0.5
        assert cached_descriptor.status_code == 200
        assert cached_descriptor.json()["data"]["mode"] == "relay_progressive"
        unauthorized_relay = anonymous_client.get(
            f"/api/projects/{project_id}/media/instances/{instance_id}/relay-file",
            headers={"Range": "bytes=0-3"},
        )
        assert unauthorized_relay.status_code == 401
        assert unauthorized_relay.json()["error"]["message"] == "Authentication required"

        result_holder: dict[str, object] = {}

        def _fetch_media() -> None:
            result_holder["response"] = anonymous_client.get(
                descriptor_data["url"],
                headers={"Range": "bytes=0-3"},
            )

        worker = Thread(target=_fetch_media)
        worker.start()
        command = websocket.receive_json()
        assert command["type"] == "stream.open"
        assert command["relativePath"] == "course-1/lesson-01.mp4"
        assert command["rangeStart"] == 0
        assert command["rangeEnd"] == 3

        upload = agent_client.put(
            f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
            headers={
                "Authorization": f"Bearer {pair_data['agentToken']}",
                "X-Content-Type": "video/mp4",
                "X-File-Size": "10",
                "X-Range-Start": "0",
                "X-Range-End": "3",
                "X-Is-Final": "false",
            },
            content=b"ab",
        )
        assert upload.status_code == 200
        upload_tail = agent_client.put(
            f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
            headers={
                "Authorization": f"Bearer {pair_data['agentToken']}",
                "X-Content-Type": "video/mp4",
                "X-File-Size": "10",
                "X-Range-Start": "0",
                "X-Range-End": "3",
                "X-Is-Final": "true",
            },
            content=b"cd",
        )
        assert upload_tail.status_code == 200
        worker.join(timeout=5)

        response = result_holder["response"]
        assert getattr(response, "status_code") == 206
        assert getattr(response, "content") == b"abcd"
        assert response.headers["Content-Range"] == "bytes 0-3/10"

        persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
        for _ in range(20):
            if len(persisted_sessions) == 1 and persisted_sessions[0].status == "COMPLETED":
                break
            time.sleep(0.05)
            persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
        assert len(persisted_sessions) == 1
        persisted = persisted_sessions[0]
        assert persisted.stream_id == command["streamId"]
        assert persisted.mode == "relay_progressive"
        assert persisted.status == "COMPLETED"
        assert persisted.range_start == 0
        assert persisted.range_end == 3
        assert persisted.bytes_from_agent == 4
        assert persisted.bytes_to_viewer == 4
        assert persisted.finished_at is not None
        diagnostic_events = get_auth_store().list_all_desktop_agent_diagnostic_events()
        assert {item.event_type for item in diagnostic_events} == {"stream_opened", "stream_completed"}


def test_desktop_agent_progressive_playback_rejects_unsupported_suffix_range(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_progressive_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert descriptor.status_code == 200
        descriptor_data = descriptor.json()["data"]

        invalid_range = browser_client.get(
            descriptor_data["url"],
            headers={"Range": "bytes=-4"},
        )
        assert invalid_range.status_code == 416
        assert invalid_range.json() == {
            "ok": False,
            "error": {
                "code": "RANGE_NOT_SATISFIABLE",
                "message": "Suffix byte ranges are not supported",
            },
        }

        persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
        assert persisted_sessions == ()


def test_desktop_agent_progressive_playback_without_range_returns_full_response(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_progressive_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert descriptor.status_code == 200
        descriptor_data = descriptor.json()["data"]

        result_holder: dict[str, object] = {}

        def _fetch_media() -> None:
            result_holder["response"] = browser_client.get(descriptor_data["url"])

        worker = Thread(target=_fetch_media)
        worker.start()
        command = websocket.receive_json()
        assert command["type"] == "stream.open"
        assert command["rangeStart"] is None
        assert command["rangeEnd"] is None

        upload = agent_client.put(
            f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
            headers={
                "Authorization": f"Bearer {pair_data['agentToken']}",
                "X-Content-Type": "video/mp4",
                "X-File-Size": "10",
                "X-Range-Start": "0",
                "X-Range-End": "9",
                "X-Is-Final": "true",
            },
            content=b"abcdefghij",
        )
        assert upload.status_code == 200
        worker.join(timeout=5)

        response = result_holder["response"]
        assert getattr(response, "status_code") == 200
        assert getattr(response, "content") == b"abcdefghij"
        assert response.headers["Content-Length"] == "10"
        assert "Content-Range" not in response.headers


def test_desktop_agent_progressive_playback_can_finish_after_agent_websocket_disconnect(auth_env: None) -> None:
    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_progressive_probe_cache(project_id, instance_id, pair_data["agentId"])

    result_holder: dict[str, object] = {}

    def _fetch_media() -> None:
        result_holder["response"] = browser_client.get(
            f"/api/projects/{project_id}/media/instances/{instance_id}/relay-file",
            headers={"Range": "bytes=0-3"},
        )

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        worker = Thread(target=_fetch_media)
        worker.start()
        command = websocket.receive_json()
        assert command["type"] == "stream.open"
        assert command["rangeStart"] == 0
        assert command["rangeEnd"] == 3

    upload = agent_client.put(
        f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
        headers={
            "Authorization": f"Bearer {pair_data['agentToken']}",
            "X-Content-Type": "video/mp4",
            "X-File-Size": "10",
            "X-Range-Start": "0",
            "X-Range-End": "3",
            "X-Is-Final": "false",
        },
        content=b"ab",
    )
    assert upload.status_code == 200
    upload_tail = agent_client.put(
        f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
        headers={
            "Authorization": f"Bearer {pair_data['agentToken']}",
            "X-Content-Type": "video/mp4",
            "X-File-Size": "10",
            "X-Range-Start": "0",
            "X-Range-End": "3",
            "X-Is-Final": "true",
        },
        content=b"cd",
    )
    assert upload_tail.status_code == 200
    worker.join(timeout=5)

    response = result_holder["response"]
    assert getattr(response, "status_code") == 206
    assert getattr(response, "content") == b"abcd"

    persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
    assert len(persisted_sessions) == 1
    persisted = persisted_sessions[0]
    assert persisted.stream_id == command["streamId"]
    assert persisted.status == "COMPLETED"
    assert persisted.failure_reason is None
    assert persisted.finished_at is not None


def test_desktop_agent_progressive_playback_fails_when_agent_disconnects_during_relay(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_AGENT_STREAM_DISCONNECT_GRACE_SECONDS", "1")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_progressive_probe_cache(project_id, instance_id, pair_data["agentId"])

    result_holder: dict[str, object] = {}

    def _fetch_media() -> None:
        result_holder["response"] = browser_client.get(
            f"/api/projects/{project_id}/media/instances/{instance_id}/relay-file",
            headers={"Range": "bytes=0-3"},
        )

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        worker = Thread(target=_fetch_media)
        worker.start()
        command = websocket.receive_json()
        assert command["type"] == "stream.open"
        assert command["rangeStart"] == 0
        assert command["rangeEnd"] == 3

    worker.join(timeout=5)

    response = result_holder["response"]
    assert getattr(response, "status_code") == 502
    assert response.json() == {
        "ok": False,
        "error": {
            "code": "BAD_GATEWAY",
            "message": "desktop agent disconnected during relay",
        },
    }

    persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
    assert len(persisted_sessions) == 1
    persisted = persisted_sessions[0]
    assert persisted.stream_id == command["streamId"]
    assert persisted.status == "FAILED"
    assert persisted.failure_reason == "desktop agent disconnected during relay"
    assert persisted.finished_at is not None


def test_desktop_agent_progressive_playback_times_out_waiting_for_headers(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_AGENT_STREAM_HEADER_TIMEOUT_SECONDS", "1")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_progressive_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert descriptor.status_code == 200
        descriptor_data = descriptor.json()["data"]

        timed_out = browser_client.get(
            descriptor_data["url"],
            headers={"Range": "bytes=0-3"},
        )
        assert timed_out.status_code == 504
        assert timed_out.json()["error"]["message"] == "desktop agent stream headers timed out"

        persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
        assert len(persisted_sessions) == 1
        persisted = persisted_sessions[0]
        assert persisted.mode == "relay_progressive"
        assert persisted.status == "FAILED"
        assert persisted.bytes_from_agent == 0
        assert persisted.bytes_to_viewer == 0
        assert persisted.failure_reason == "desktop agent stream headers timed out"


def test_desktop_agent_progressive_playback_rejects_concurrent_streams_over_limit(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLM_AGENT_MAX_CONCURRENT_STREAMS_PER_AGENT", "1")
    _reset_caches()

    app = create_app()
    owner_client = TestClient(app)
    browser_client = TestClient(app)
    second_browser_client = TestClient(app)
    agent_client = TestClient(app)

    owner_client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "password123"},
    )
    browser_login = browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert browser_login.status_code == 200
    second_browser_login = second_browser_client.post(
        "/api/auth/login",
        json={"email": "owner@example.com", "password": "password123"},
    )
    assert second_browser_login.status_code == 200
    created = owner_client.post("/api/projects", json={"title": "Hosted Project"})
    project_id = created.json()["data"]["projectId"]

    pairing = owner_client.post("/api/desktop-agents/pairing-codes")
    paired = owner_client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    pair_data = paired.json()["data"]
    owner_client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": pair_data["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    owner_client.post(
        "/api/desktop-agents/manifest-sync",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
        json={
            "projectId": project_id,
            "agentId": pair_data["agentId"],
            "rootTitle": "Videos",
            "entries": [{"relativePath": "course-1/lesson-01.mp4"}],
        },
    )
    instances = owner_client.get(f"/api/projects/{project_id}/instances")
    assert instances.status_code == 200
    instance_id = instances.json()["data"][0]["instanceId"]
    _seed_progressive_probe_cache(project_id, instance_id, pair_data["agentId"])

    with agent_client.websocket_connect(
        "/api/desktop-agents/ws",
        headers={"Authorization": f"Bearer {pair_data['agentToken']}"},
    ) as websocket:
        assert websocket.receive_json()["type"] == "connected"
        websocket.send_json(
            {
                "type": "hello",
                "agentId": pair_data["agentId"],
                "deviceName": "BYLOU-PC",
                "appVersion": "0.1.0",
            }
        )
        assert websocket.receive_json()["type"] == "hello.ack"

        descriptor = owner_client.get(f"/api/projects/{project_id}/media/instances/{instance_id}/playback")
        assert descriptor.status_code == 200
        descriptor_data = descriptor.json()["data"]

        result_holder: dict[str, object] = {}

        def _fetch_first_media() -> None:
            result_holder["response"] = browser_client.get(
                descriptor_data["url"],
                headers={"Range": "bytes=0-3"},
            )

        worker = Thread(target=_fetch_first_media)
        worker.start()
        command = websocket.receive_json()
        assert command["type"] == "stream.open"

        denied = second_browser_client.get(
            descriptor_data["url"],
            headers={"Range": "bytes=4-7"},
        )
        assert denied.status_code == 409
        assert denied.json()["error"]["message"] == "desktop agent concurrent stream limit reached"

        upload = agent_client.put(
            f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
            headers={
                "Authorization": f"Bearer {pair_data['agentToken']}",
                "X-Content-Type": "video/mp4",
                "X-File-Size": "10",
                "X-Range-Start": "0",
                "X-Range-End": "3",
                "X-Is-Final": "false",
            },
            content=b"ab",
        )
        assert upload.status_code == 200
        upload_tail = agent_client.put(
            f"/api/desktop-agents/stream-sessions/{command['streamId']}/chunks",
            headers={
                "Authorization": f"Bearer {pair_data['agentToken']}",
                "X-Content-Type": "video/mp4",
                "X-File-Size": "10",
                "X-Range-Start": "0",
                "X-Range-End": "3",
                "X-Is-Final": "true",
            },
            content=b"cd",
        )
        assert upload_tail.status_code == 200
        worker.join(timeout=5)

        response = result_holder["response"]
        assert getattr(response, "status_code") == 206
        assert getattr(response, "content") == b"abcd"

        persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
        for _ in range(20):
            if len(persisted_sessions) == 1 and persisted_sessions[0].status == "COMPLETED":
                break
            time.sleep(0.05)
            persisted_sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
        assert len(persisted_sessions) == 1
        assert persisted_sessions[0].status == "COMPLETED"
