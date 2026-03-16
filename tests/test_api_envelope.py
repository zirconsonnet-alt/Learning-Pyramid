import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapter.desktop_agent_alert_webhooks import reset_desktop_agent_alert_webhook_dispatcher
from adapter.deps import get_api, get_auth_store, get_desktop_agent_runtime
from adapter.desktop_agent_hls_job_audit import persist_runtime_hls_job_audit
from adapter.desktop_agent_janitor import collect_desktop_agent_relay_status
from adapter.errors import register_exception_handlers
from adapter.main import create_app
from backend.models.desktop_agent_metric_sample import DesktopAgentMetricSample
from backend.models.enums import DesktopAgentStatus
from backend.models.hls_cache_entry import HlsCacheEntry
from backend.models.media_stream_session import MediaStreamSession


def _reset_caches() -> None:
    get_api.cache_clear()
    get_auth_store.cache_clear()
    get_desktop_agent_runtime.cache_clear()
    reset_desktop_agent_alert_webhook_dispatcher()


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
            "sqlBackend": "sqlite",
            "ready": True,
        },
    }


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


def test_system_runtime_reports_desktop_agent_relay_metrics(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "false")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_AGENT_CACHE_DIR", str(tmp_path / "desktop-cache"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    project_id = get_api().create_project("Runtime Metrics", project_root=str(tmp_path / "project-runtime"))
    auth_store = get_auth_store()
    user = auth_store.create_user("runtime@example.com", "password123")
    auth_store.add_project_owner(str(project_id), user.user_id)
    pairing = auth_store.create_desktop_agent_pairing_code(user.user_id)
    agent, _, _ = auth_store.pair_desktop_agent(
        pairing.pairing_code,
        device_name="BYLOU-PC",
        platform="windows",
        app_version="0.1.0",
    )

    runtime = get_desktop_agent_runtime()
    runtime.register_connection(agent.agent_id, object())  # type: ignore[arg-type]
    runtime.create_stream_session(
        agent_id=agent.agent_id,
        user_id=user.user_id,
        project_id=str(project_id),
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=120,
    )
    runtime.create_probe_request(
        agent_id=agent.agent_id,
        project_id=str(project_id),
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
    )
    runtime.create_or_get_hls_job(
        cache_key="cache_123",
        agent_id=agent.agent_id,
        project_id=str(project_id),
        instance_id="inst_123",
        relative_path="lesson-01.mkv",
        profile={"heightMax": 720},
    )
    cache_file = tmp_path / "desktop-cache" / "cache_123" / "master.m3u8"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text("#EXTM3U\n", encoding="utf-8")
    auth_store.upsert_hls_cache_entry(
        HlsCacheEntry(
            cache_key="cache_123",
            project_id=str(project_id),
            instance_id="inst_123",
            agent_id=agent.agent_id,
            profile='{"heightMax":720}',
            segment_name="master.m3u8",
                file_path=str(cache_file),
                size_bytes=len(cache_file.read_bytes()),
                created_at="2026-03-11T12:00:00+00:00",
                last_accessed_at="2026-03-11T12:00:00+00:00",
                expires_at="2026-03-20T12:00:00+00:00",
            )
        )

    client = TestClient(create_app())
    resp = client.get("/api/system/runtime")

    assert resp.status_code == 200
    relay = resp.json()["data"]["desktopAgentRelay"]
    assert relay["available"] is True
    assert relay["connectedAgentCount"] == 1
    assert "connectedAgentIds" not in relay
    assert relay["activeStreamCount"] == 1
    assert relay["pendingProbeCount"] == 1
    assert relay["activeHlsJobCount"] == 1
    assert relay["hlsCacheEntryCount"] == 1
    assert relay["hlsCacheBytes"] == len(cache_file.read_bytes())
    assert relay["hlsCachePrunedCount"] == 0
    assert relay["hlsCacheRequestCount"] == 0
    assert relay["hlsCacheHitCount"] == 0
    assert relay["hlsCacheMissCount"] == 0
    assert relay["hlsCacheHitRate"] is None
    assert relay["hlsArtifactRequestCount"] == 0
    assert relay["hlsArtifactBytesServed"] == 0
    assert relay["persistedHlsJobAuditCount"] == 0
    assert relay["persistedExpiredHlsJobCount"] == 0
    assert relay["metricSampleBucketSeconds"] == 300
    assert relay["metricSampleRetentionDays"] == 30
    assert relay["persistedMetricSampleCount"] == 1
    assert relay["persistedDiagnosticEventCount"] == 0
    assert relay["sampledMetricProjectCount"] == 1
    assert relay["prunedMetricSampleCount"] == 0
    assert relay["prunedDiagnosticEventCount"] == 0
    assert relay["reapedStreamCount"] == 0
    assert relay["reapedProbeCount"] == 0
    assert relay["reapedHlsJobCount"] == 0
    assert relay["reapReasonCounts"] == {}


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


def test_desktop_agent_alert_webhook_dispatches_only_on_maintenance_pass(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_AGENT_ALERT_WEBHOOK_URL", "https://example.com/hooks/relay")
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    calls: list[dict[str, object]] = []

    class _WebhookResponse:
        def raise_for_status(self) -> None:
            return None

    def _fake_post(url: str, *, json: object, timeout: float):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _WebhookResponse()

    reset_desktop_agent_alert_webhook_dispatcher(_fake_post)
    client = TestClient(create_app())
    register_resp = client.post("/api/auth/register", json={"email": "hook@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Relay Alerts"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    pairing_resp = client.post("/api/desktop-agents/pairing-codes")
    assert pairing_resp.status_code == 200
    pair_resp = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_resp.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert pair_resp.status_code == 200
    paired_agent = get_auth_store().get_desktop_agent(pair_resp.json()["data"]["agentId"])
    now = datetime.now(timezone.utc).replace(microsecond=0)
    diagnostic_resp = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {pair_resp.json()['data']['agentToken']}"},
        json={
            "level": "error",
            "category": "hls",
            "eventType": "hls_failed",
            "message": "ffmpeg missing",
            "details": {"jobId": "job_alert"},
            "projectId": str(project_id),
            "instanceId": "inst_alert",
            "relativePath": "lesson-09.mkv",
            "createdAt": now.isoformat(),
        },
    )
    assert diagnostic_resp.status_code == 200

    runtime_resp = client.get("/api/system/runtime")
    assert runtime_resp.status_code == 200
    assert calls == []
    assert runtime_resp.json()["data"]["desktopAgentRelay"]["alertWebhook"] == {
        "channels": [
            {
                "name": "primary",
                "url": "https://example.com/hooks/relay",
                "status": "IDLE",
                "lastAttemptAt": None,
                "lastSuccessAt": None,
                "lastError": None,
                "sentCount": 0,
                "suppressedCount": 0,
                "failedCount": 0,
                "lastAlertCount": 0,
                "nextRetryAt": None,
                "retryPending": False,
                "consecutiveFailureCount": 0,
            }
        ],
        "configured": True,
        "windowHours": 1,
        "cooldownSeconds": 900,
        "retryBackoffSeconds": 60,
        "retryMaxBackoffSeconds": 900,
        "channelCount": 1,
        "healthyChannelCount": 1,
        "retryingChannelCount": 0,
        "failingChannelCount": 0,
        "lastAttemptAt": None,
        "lastSuccessAt": None,
        "lastError": None,
        "sentCount": 0,
        "suppressedCount": 0,
        "failedCount": 0,
        "lastAlertCount": 0,
    }

    report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=get_auth_store(),
        dispatch_alert_webhooks=True,
    )
    assert report["alertWebhook"]["configured"] is True
    assert report["alertWebhook"]["sentCount"] == 1
    assert report["alertWebhook"]["suppressedCount"] == 0
    assert report["alertWebhook"]["lastAlertCount"] == 1
    assert report["alertWebhook"]["lastAttemptAt"] is not None
    assert report["alertWebhook"]["lastSuccessAt"] is not None
    assert report["alertWebhook"]["lastError"] is None
    assert report["alertWebhook"]["channelCount"] == 1
    assert report["alertWebhook"]["healthyChannelCount"] == 1
    assert report["alertWebhook"]["retryingChannelCount"] == 0
    assert report["alertWebhook"]["failingChannelCount"] == 0
    assert report["alertWebhook"]["failedCount"] == 0
    assert report["alertWebhook"]["channels"] == [
        {
            "name": "primary",
            "url": "https://example.com/hooks/relay",
            "status": "HEALTHY",
            "lastAttemptAt": report["alertWebhook"]["lastAttemptAt"],
            "lastSuccessAt": report["alertWebhook"]["lastSuccessAt"],
            "lastError": None,
            "sentCount": 1,
            "suppressedCount": 0,
            "failedCount": 0,
            "lastAlertCount": 1,
            "nextRetryAt": None,
            "retryPending": False,
            "consecutiveFailureCount": 0,
        }
    ]
    assert len(calls) == 1
    assert calls[0]["url"] == "https://example.com/hooks/relay"
    assert calls[0]["timeout"] == 5.0
    webhook_body = calls[0]["json"]
    assert webhook_body == {
        "source": "desktop-agent-relay",
        "sentAt": report["alertWebhook"]["lastSuccessAt"],
        "windowHours": 1,
        "alertCount": 1,
        "alerts": [
                {
                    "severity": "error",
                    "userId": paired_agent.user_id,
                    "agentId": pair_resp.json()["data"]["agentId"],
                "projectId": str(project_id),
                "category": "hls",
                "code": "hls_failed",
                "title": "hls: hls_failed",
                "message": "ffmpeg missing",
                "observedAt": now.isoformat(),
                "count": 1,
            }
        ],
    }

    second_report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=get_auth_store(),
        dispatch_alert_webhooks=True,
    )
    assert second_report["alertWebhook"]["sentCount"] == 1
    assert second_report["alertWebhook"]["suppressedCount"] == 1
    assert second_report["alertWebhook"]["failedCount"] == 0
    assert second_report["alertWebhook"]["channels"][0]["suppressedCount"] == 1
    assert len(calls) == 1


def test_desktop_agent_alert_webhook_suppresses_recovered_transient_disconnect_alerts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_AGENT_ALERT_WEBHOOK_URL", "https://example.com/hooks/recovered-transient")
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    calls: list[dict[str, object]] = []

    class _WebhookResponse:
        def raise_for_status(self) -> None:
            return None

    def _fake_post(url: str, *, json: object, timeout: float):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _WebhookResponse()

    reset_desktop_agent_alert_webhook_dispatcher(_fake_post)
    client = TestClient(create_app())
    register_resp = client.post(
        "/api/auth/register",
        json={"email": "recovered-hook@example.com", "password": "password123"},
    )
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Recovered Transient Alerts"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    pairing_resp = client.post("/api/desktop-agents/pairing-codes")
    assert pairing_resp.status_code == 200
    pair_resp = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_resp.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert pair_resp.status_code == 200

    observed_at = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)
    auth_headers = {"Authorization": f"Bearer {pair_resp.json()['data']['agentToken']}"}
    diagnostic_payloads = [
        {
            "level": "warning",
            "category": "service",
            "eventType": "connection_lost",
            "message": "websocket disconnected",
            "details": {"projectId": str(project_id)},
            "projectId": str(project_id),
            "createdAt": observed_at.isoformat(),
        },
        {
            "level": "warning",
            "category": "service",
            "eventType": "ws_invalid_message",
            "message": "received invalid websocket frame",
            "details": {"projectId": str(project_id)},
            "projectId": str(project_id),
            "createdAt": observed_at.isoformat(),
        },
        {
            "level": "error",
            "category": "service",
            "eventType": "session_failed",
            "message": "desktop agent session aborted",
            "details": {"projectId": str(project_id)},
            "projectId": str(project_id),
            "createdAt": observed_at.isoformat(),
        },
        {
            "level": "info",
            "category": "stream",
            "eventType": "stream_completed",
            "message": "progressive relay recovered and finished",
            "details": {"streamId": "stream_recovered"},
            "projectId": str(project_id),
            "instanceId": "inst_recovered",
            "relativePath": "lesson-11.mp4",
            "createdAt": observed_at.isoformat(),
        },
    ]
    for payload in diagnostic_payloads:
        diagnostic_resp = client.post(
            "/api/desktop-agents/diagnostic-events",
            headers=auth_headers,
            json=payload,
        )
        assert diagnostic_resp.status_code == 200

    persisted_event_types = {
        str(item.event_type)
        for item in get_auth_store().list_all_desktop_agent_diagnostic_events(
            since=(observed_at - timedelta(minutes=1)).isoformat()
        )
    }
    assert {
        "connection_lost",
        "ws_invalid_message",
        "session_failed",
        "stream_completed",
    } <= persisted_event_types

    report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=get_auth_store(),
        dispatch_alert_webhooks=True,
        now=observed_at + timedelta(minutes=1),
    )
    assert report["alertWebhook"]["configured"] is True
    assert report["alertWebhook"]["sentCount"] == 0
    assert report["alertWebhook"]["suppressedCount"] == 0
    assert report["alertWebhook"]["failedCount"] == 0
    assert report["alertWebhook"]["lastAlertCount"] == 0
    assert report["alertWebhook"]["lastAttemptAt"] is None
    assert report["alertWebhook"]["lastSuccessAt"] is None
    assert report["alertWebhook"]["lastError"] is None
    assert report["alertWebhook"]["channelCount"] == 1
    assert report["alertWebhook"]["healthyChannelCount"] == 1
    assert report["alertWebhook"]["retryingChannelCount"] == 0
    assert report["alertWebhook"]["failingChannelCount"] == 0
    assert report["alertWebhook"]["channels"] == [
        {
            "name": "primary",
            "url": "https://example.com/hooks/recovered-transient",
            "status": "IDLE",
            "lastAttemptAt": None,
            "lastSuccessAt": None,
            "lastError": None,
            "sentCount": 0,
            "suppressedCount": 0,
            "failedCount": 0,
            "lastAlertCount": 0,
            "nextRetryAt": None,
            "retryPending": False,
            "consecutiveFailureCount": 0,
        }
    ]
    assert calls == []


def test_desktop_agent_alert_webhook_retries_failed_channel_and_supports_multiple_targets(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv(
        "PLM_AGENT_ALERT_WEBHOOK_TARGETS",
        json.dumps(
            [
                {"name": "ops-primary", "url": "https://example.com/hooks/ops-primary"},
                {"name": "ops-secondary", "url": "https://example.com/hooks/ops-secondary"},
            ]
        ),
    )
    monkeypatch.delenv("PLM_AGENT_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("PLM_AGENT_ALERT_WEBHOOK_RETRY_BACKOFF_SECONDS", "60")
    monkeypatch.setenv("PLM_AGENT_ALERT_WEBHOOK_RETRY_MAX_BACKOFF_SECONDS", "300")
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    calls: list[dict[str, object]] = []

    class _WebhookResponse:
        def raise_for_status(self) -> None:
            return None

    def _fake_post(url: str, *, json: object, timeout: float):
        calls.append({"url": url, "json": json, "timeout": timeout})
        if url.endswith("ops-primary") and sum(1 for item in calls if item["url"] == url) == 1:
            raise RuntimeError("ops-primary temporary failure")
        return _WebhookResponse()

    reset_desktop_agent_alert_webhook_dispatcher(_fake_post)
    client = TestClient(create_app())
    register_resp = client.post("/api/auth/register", json={"email": "multi-hook@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Relay Multi Alerts"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    pairing_resp = client.post("/api/desktop-agents/pairing-codes")
    assert pairing_resp.status_code == 200
    pair_resp = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_resp.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert pair_resp.status_code == 200
    first_pass_at = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)
    diagnostic_resp = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {pair_resp.json()['data']['agentToken']}"},
        json={
            "level": "error",
            "category": "stream",
            "eventType": "stream_open_failed",
            "message": "relay upload stalled",
            "details": {"streamId": "stream_retry"},
            "projectId": str(project_id),
            "instanceId": "inst_retry",
            "relativePath": "lesson-10.mp4",
            "createdAt": first_pass_at.isoformat(),
        },
    )
    assert diagnostic_resp.status_code == 200

    first_report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=get_auth_store(),
        dispatch_alert_webhooks=True,
        now=first_pass_at,
    )
    assert first_report["alertWebhook"]["channelCount"] == 2
    assert first_report["alertWebhook"]["healthyChannelCount"] == 1
    assert first_report["alertWebhook"]["retryingChannelCount"] == 1
    assert first_report["alertWebhook"]["failingChannelCount"] == 1
    assert first_report["alertWebhook"]["sentCount"] == 1
    assert first_report["alertWebhook"]["failedCount"] == 1
    assert first_report["alertWebhook"]["suppressedCount"] == 0
    assert len(calls) == 2
    primary_channel = next(item for item in first_report["alertWebhook"]["channels"] if item["name"] == "ops-primary")
    secondary_channel = next(item for item in first_report["alertWebhook"]["channels"] if item["name"] == "ops-secondary")
    assert primary_channel["status"] == "RETRYING"
    assert primary_channel["failedCount"] == 1
    assert primary_channel["retryPending"] is True
    assert primary_channel["nextRetryAt"] == "2026-03-11T12:01:00+00:00"
    assert primary_channel["lastError"] == "ops-primary temporary failure"
    assert secondary_channel["status"] == "HEALTHY"
    assert secondary_channel["sentCount"] == 1

    second_report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=get_auth_store(),
        dispatch_alert_webhooks=True,
        now=first_pass_at + timedelta(seconds=30),
    )
    assert second_report["alertWebhook"]["sentCount"] == 1
    assert second_report["alertWebhook"]["failedCount"] == 1
    assert second_report["alertWebhook"]["suppressedCount"] == 1
    assert second_report["alertWebhook"]["retryingChannelCount"] == 1
    assert len(calls) == 2

    third_report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=get_auth_store(),
        dispatch_alert_webhooks=True,
        now=first_pass_at + timedelta(seconds=61),
    )
    assert third_report["alertWebhook"]["healthyChannelCount"] == 2
    assert third_report["alertWebhook"]["retryingChannelCount"] == 0
    assert third_report["alertWebhook"]["failingChannelCount"] == 0
    assert third_report["alertWebhook"]["sentCount"] == 2
    assert third_report["alertWebhook"]["failedCount"] == 1
    assert third_report["alertWebhook"]["suppressedCount"] == 2
    assert len(calls) == 3
    primary_channel = next(item for item in third_report["alertWebhook"]["channels"] if item["name"] == "ops-primary")
    secondary_channel = next(item for item in third_report["alertWebhook"]["channels"] if item["name"] == "ops-secondary")
    assert primary_channel["status"] == "HEALTHY"
    assert primary_channel["sentCount"] == 1
    assert primary_channel["failedCount"] == 1
    assert primary_channel["retryPending"] is False
    assert primary_channel["consecutiveFailureCount"] == 0
    assert secondary_channel["suppressedCount"] == 2


def test_desktop_agent_alert_webhook_supports_builtin_log_channel(
    monkeypatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv(
        "PLM_AGENT_ALERT_WEBHOOK_TARGETS",
        json.dumps([{"name": "ops-log", "url": "builtin://log"}]),
    )
    monkeypatch.delenv("PLM_AGENT_ALERT_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    def _unexpected_post(*args, **kwargs):
        raise AssertionError("builtin log channel should not perform HTTP POST")

    reset_desktop_agent_alert_webhook_dispatcher(_unexpected_post)
    client = TestClient(create_app())
    register_resp = client.post("/api/auth/register", json={"email": "builtin-hook@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Relay Builtin Alerts"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    pairing_resp = client.post("/api/desktop-agents/pairing-codes")
    assert pairing_resp.status_code == 200
    pair_resp = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_resp.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert pair_resp.status_code == 200

    diagnostic_resp = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {pair_resp.json()['data']['agentToken']}"},
        json={
            "level": "warning",
            "category": "probe",
            "eventType": "probe_missing_tool",
            "message": "ffprobe missing",
            "details": {"tool": "ffprobe"},
            "projectId": str(project_id),
            "instanceId": "inst_builtin",
            "relativePath": "lesson-11.mp4",
            "createdAt": "2026-03-11T12:00:00+00:00",
        },
    )
    assert diagnostic_resp.status_code == 200

    with caplog.at_level(logging.WARNING, logger="adapter.desktop_agent_alert_webhooks"):
        report = collect_desktop_agent_relay_status(
            runtime=get_desktop_agent_runtime(),
            auth_store=get_auth_store(),
            dispatch_alert_webhooks=True,
            now=datetime(2026, 3, 11, 12, 5, 0, tzinfo=timezone.utc),
        )

    assert report["alertWebhook"]["channelCount"] == 1
    assert report["alertWebhook"]["healthyChannelCount"] == 1
    assert report["alertWebhook"]["sentCount"] == 1
    assert report["alertWebhook"]["failedCount"] == 0
    assert report["alertWebhook"]["channels"] == [
        {
            "name": "ops-log",
            "url": "builtin://log",
            "status": "HEALTHY",
            "lastAttemptAt": "2026-03-11T12:05:00+00:00",
            "lastSuccessAt": "2026-03-11T12:05:00+00:00",
            "lastError": None,
            "sentCount": 1,
            "suppressedCount": 0,
            "failedCount": 0,
            "lastAlertCount": 1,
            "nextRetryAt": None,
            "retryPending": False,
            "consecutiveFailureCount": 0,
        }
    ]
    assert "desktop_agent_relay_alert channel=ops-log" in caplog.text
    assert '"code": "probe_missing_tool"' in caplog.text


def test_system_relay_monitor_reports_user_agents_recent_issues_and_hls_jobs(monkeypatch, tmp_path: Path) -> None:
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
    register_resp = client.post("/api/auth/register", json={"email": "monitor@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Relay Monitor"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    pairing_resp = client.post("/api/desktop-agents/pairing-codes")
    assert pairing_resp.status_code == 200
    pairing_code = pairing_resp.json()["data"]["pairingCode"]
    pair_resp = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_code,
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert pair_resp.status_code == 200
    agent_id = pair_resp.json()["data"]["agentId"]
    bind_resp = client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": agent_id,
            "sourceRootLabel": "Videos",
        },
    )
    assert bind_resp.status_code == 200

    auth_store = get_auth_store()
    runtime = get_desktop_agent_runtime()
    agent = auth_store.get_desktop_agent(agent_id)
    runtime.register_connection(agent.agent_id, object())  # type: ignore[arg-type]
    runtime.enqueue_command(agent.agent_id, {"type": "stream.cancel", "streamId": "stream_pending"})
    runtime.create_stream_session(
        agent_id=agent.agent_id,
        user_id=agent.user_id,
        project_id=str(project_id),
        instance_id="inst_open",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=120,
    )
    runtime.create_probe_request(
        agent_id=agent.agent_id,
        project_id=str(project_id),
        instance_id="inst_probe",
        relative_path="lesson-02.mp4",
    )
    job, _ = runtime.create_or_get_hls_job(
        cache_key="cache_monitor",
        agent_id=agent.agent_id,
        project_id=str(project_id),
        instance_id="inst_hls",
        relative_path="lesson-03.mkv",
        profile={"heightMax": 720},
    )
    runtime.update_hls_job_state(job.job_id, agent_id=agent.agent_id, state="FAILED", message="ffmpeg exited 1")
    persist_runtime_hls_job_audit(auth_store, runtime.get_hls_job(job.job_id))

    created_at = "2026-03-11T12:00:00+00:00"
    completed_at = "2026-03-11T12:02:00+00:00"
    cancelled_at = "2026-03-11T12:03:00+00:00"
    failed_at = "2026-03-11T12:04:00+00:00"
    auth_store.create_media_stream_session(
        MediaStreamSession(
            stream_id="stream_completed",
            project_id=str(project_id),
            instance_id="inst_completed",
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            mode="relay_progressive",
            status="COMPLETED",
            range_start=0,
            range_end=255,
            bytes_from_agent=4096,
            bytes_to_viewer=4096,
            created_at=created_at,
            updated_at=completed_at,
            expires_at="2026-03-11T13:00:00+00:00",
            finished_at=completed_at,
            failure_reason=None,
        )
    )
    auth_store.create_media_stream_session(
        MediaStreamSession(
            stream_id="stream_cancelled",
            project_id=str(project_id),
            instance_id="inst_cancelled",
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            mode="relay_progressive",
            status="CANCELLED",
            range_start=None,
            range_end=None,
            bytes_from_agent=2048,
            bytes_to_viewer=1024,
            created_at=created_at,
            updated_at=cancelled_at,
            expires_at="2026-03-11T13:00:00+00:00",
            finished_at=cancelled_at,
            failure_reason="viewer disconnected during relay",
        )
    )
    auth_store.create_media_stream_session(
        MediaStreamSession(
            stream_id="stream_failed",
            project_id=str(project_id),
            instance_id="inst_failed",
            agent_id=agent.agent_id,
            user_id=agent.user_id,
            mode="relay_progressive",
            status="FAILED",
            range_start=None,
            range_end=None,
            bytes_from_agent=512,
            bytes_to_viewer=0,
            created_at=created_at,
            updated_at=failed_at,
            expires_at="2026-03-11T13:00:00+00:00",
            finished_at=failed_at,
            failure_reason="desktop agent disconnected during relay",
        )
    )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    auth_store.upsert_desktop_agent_metric_sample(
        DesktopAgentMetricSample(
            project_id=str(project_id),
            bucket_start=(now - timedelta(days=10)).isoformat(),
            bucket_seconds=300,
            captured_at=(now - timedelta(days=10) + timedelta(minutes=1)).isoformat(),
            session_count=0,
            active_stream_count=0,
            completed_stream_count=0,
            failed_stream_count=0,
            cancelled_stream_count=0,
            bytes_from_agent_total=256,
            bytes_to_viewer_total=128,
            hls_job_count=0,
            active_hls_job_count=0,
            completed_hls_job_count=0,
            failed_hls_job_count=0,
            cancelled_hls_job_count=0,
            hls_artifact_bytes_total=0,
            hls_cache_entry_count=0,
            hls_cache_bytes=0,
        )
    )
    auth_store.upsert_desktop_agent_metric_sample(
        DesktopAgentMetricSample(
            project_id=str(project_id),
            bucket_start=(now - timedelta(days=3)).isoformat(),
            bucket_seconds=300,
            captured_at=(now - timedelta(days=3) + timedelta(minutes=1)).isoformat(),
            session_count=1,
            active_stream_count=0,
            completed_stream_count=0,
            failed_stream_count=0,
            cancelled_stream_count=0,
            bytes_from_agent_total=768,
            bytes_to_viewer_total=512,
            hls_job_count=0,
            active_hls_job_count=0,
            completed_hls_job_count=0,
            failed_hls_job_count=0,
            cancelled_hls_job_count=0,
            hls_artifact_bytes_total=0,
            hls_cache_entry_count=0,
            hls_cache_bytes=0,
        )
    )
    auth_store.upsert_desktop_agent_metric_sample(
        DesktopAgentMetricSample(
            project_id=str(project_id),
            bucket_start=(now - timedelta(hours=2)).isoformat(),
            bucket_seconds=300,
            captured_at=(now - timedelta(hours=2) + timedelta(minutes=1)).isoformat(),
            session_count=1,
            active_stream_count=0,
            completed_stream_count=0,
            failed_stream_count=0,
            cancelled_stream_count=0,
            bytes_from_agent_total=1024,
            bytes_to_viewer_total=512,
            hls_job_count=0,
            active_hls_job_count=0,
            completed_hls_job_count=0,
            failed_hls_job_count=0,
            cancelled_hls_job_count=0,
            hls_artifact_bytes_total=0,
            hls_cache_entry_count=0,
            hls_cache_bytes=0,
        )
    )
    auth_store.upsert_desktop_agent_metric_sample(
        DesktopAgentMetricSample(
            project_id=str(project_id),
            bucket_start=(now - timedelta(hours=1)).isoformat(),
            bucket_seconds=300,
            captured_at=(now - timedelta(hours=1) + timedelta(minutes=1)).isoformat(),
            session_count=3,
            active_stream_count=0,
            completed_stream_count=1,
            failed_stream_count=1,
            cancelled_stream_count=1,
            bytes_from_agent_total=6656,
            bytes_to_viewer_total=5120,
            hls_job_count=1,
            active_hls_job_count=0,
            completed_hls_job_count=0,
            failed_hls_job_count=1,
            cancelled_hls_job_count=0,
            hls_artifact_bytes_total=0,
            hls_cache_entry_count=0,
            hls_cache_bytes=0,
        )
    )
    diagnostic_resp = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {pair_resp.json()['data']['agentToken']}"},
        json={
            "level": "error",
            "category": "hls",
            "eventType": "hls_failed",
            "message": "ffmpeg missing",
            "details": {"jobId": job.job_id},
            "projectId": str(project_id),
            "instanceId": "inst_hls",
            "relativePath": "lesson-03.mkv",
            "createdAt": now.isoformat(),
        },
    )
    assert diagnostic_resp.status_code == 200
    older_warning_at = (now - timedelta(days=3)).isoformat()
    warning_diagnostic_resp = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {pair_resp.json()['data']['agentToken']}"},
        json={
            "level": "warning",
            "category": "manifest",
            "eventType": "manifest_sync_failed",
            "message": "archive path missing",
            "details": {"root": "archive"},
            "projectId": str(project_id),
            "instanceId": "inst_manifest",
            "relativePath": "archive/index.json",
            "createdAt": older_warning_at,
        },
    )
    assert warning_diagnostic_resp.status_code == 200

    resp = client.get("/api/system/relay-monitor")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["available"] is True
    assert body["projectCount"] == 1
    assert body["projectIds"] == [str(project_id)]
    assert body["bindingSummary"] == {
        "desktopAgentProjectCount": 1,
        "boundOnlineProjectCount": 1,
        "boundOfflineProjectCount": 0,
        "serverFsProjectCount": 0,
        "supersededBindingCount": 0,
    }
    assert body["projectBindings"] == [
        {
            "projectId": str(project_id),
            "projectTitle": "Relay Monitor",
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": agent.agent_id,
            "sourceRootLabel": "Videos",
            "deviceName": "BYLOU-PC",
            "appVersion": "0.1.0",
            "lastSeenAt": agent.last_seen_at,
            "pairedAt": agent.paired_at,
            "connected": True,
            "connectionState": "CONNECTED",
            "bindingState": "ONLINE",
            "supersededByAgentId": None,
        }
    ]
    assert body["agentCount"] == 1
    assert body["agents"] == [
        {
            "agentId": agent.agent_id,
            "userId": agent.user_id,
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
            "status": "ONLINE",
            "lastSeenAt": agent.last_seen_at,
            "pairedAt": agent.paired_at,
            "connected": True,
            "connectionState": "CONNECTED",
            "queuedCommandCount": 1,
            "activeStreamCount": 1,
            "pendingProbeCount": 1,
            "activeHlsJobCount": 0,
            "hlsJobCount": 1,
        }
    ]
    assert body["streamSummary"] == {
        "sessionCount": 3,
        "activeSessionCount": 0,
        "failedSessionCount": 1,
        "cancelledSessionCount": 1,
        "completedSessionCount": 1,
        "bytesFromAgentTotal": 6656,
        "bytesToViewerTotal": 5120,
        "sessionsByStatus": {
            "CANCELLED": 1,
            "COMPLETED": 1,
            "FAILED": 1,
        },
        "issueReasonCounts": {
            "desktop agent disconnected during relay": 1,
            "viewer disconnected during relay": 1,
        },
    }
    assert body["recentIssues"] == [
        {
            "streamId": "stream_failed",
            "projectId": str(project_id),
            "projectTitle": "Relay Monitor",
            "instanceId": "inst_failed",
            "agentId": agent.agent_id,
            "mode": "relay_progressive",
            "status": "FAILED",
            "rangeStart": None,
            "rangeEnd": None,
            "bytesFromAgent": 512,
            "bytesToViewer": 0,
            "createdAt": created_at,
            "updatedAt": failed_at,
            "expiresAt": "2026-03-11T13:00:00+00:00",
            "finishedAt": failed_at,
            "failureReason": "desktop agent disconnected during relay",
        },
        {
            "streamId": "stream_cancelled",
            "projectId": str(project_id),
            "projectTitle": "Relay Monitor",
            "instanceId": "inst_cancelled",
            "agentId": agent.agent_id,
            "mode": "relay_progressive",
            "status": "CANCELLED",
            "rangeStart": None,
            "rangeEnd": None,
            "bytesFromAgent": 2048,
            "bytesToViewer": 1024,
            "createdAt": created_at,
            "updatedAt": cancelled_at,
            "expiresAt": "2026-03-11T13:00:00+00:00",
            "finishedAt": cancelled_at,
            "failureReason": "viewer disconnected during relay",
        },
    ]
    assert body["hlsSummary"] == {
        "jobCount": 1,
        "activeHlsJobCount": 0,
        "jobsByState": {"FAILED": 1},
        "issueReasonCounts": {"ffmpeg exited 1": 1},
        "activityWindows": {
            "lastHour": {
                "jobCount": 1,
                "completedCount": 0,
                "failedCount": 1,
                "cancelledCount": 0,
                "artifactBytes": 0,
            },
            "lastDay": {
                "jobCount": 1,
                "completedCount": 0,
                "failedCount": 1,
                "cancelledCount": 0,
                "artifactBytes": 0,
            },
        },
    }
    assert body["recentHlsJobs"] == [
        {
            "jobId": job.job_id,
            "cacheKey": "cache_monitor",
            "agentId": agent.agent_id,
            "projectId": str(project_id),
            "instanceId": "inst_hls",
            "relativePath": "lesson-03.mkv",
            "profile": {"heightMax": 720},
            "createdAt": job.created_at,
            "updatedAt": job.updated_at,
            "expiresAt": job.expires_at,
            "state": "FAILED",
            "message": "ffmpeg exited 1",
            "startedAt": job.started_at,
            "finishedAt": job.finished_at,
            "lastArtifactAt": None,
            "connectionLostAt": None,
            "artifactCount": 0,
            "artifactBytes": 0,
        }
    ]
    assert body["diagnosticSummary"] == {
        "eventCount": 1,
        "errorCount": 1,
        "warningCount": 0,
        "eventsByCategory": {"hls": 1},
        "eventsByLevel": {"ERROR": 1},
        "eventsByType": {"hls_failed": 1},
    }
    assert body["recentDiagnostics"] == [
        {
            "eventId": diagnostic_resp.json()["data"]["eventId"],
            "agentId": agent.agent_id,
            "projectId": str(project_id),
            "instanceId": "inst_hls",
            "relativePath": "lesson-03.mkv",
            "level": "ERROR",
            "category": "hls",
            "eventType": "hls_failed",
            "message": "ffmpeg missing",
            "details": {"jobId": job.job_id},
            "createdAt": now.isoformat(),
        }
    ]
    assert body["alerts"] == [
        {
            "severity": "error",
            "code": "hls_failed",
            "title": "hls: hls_failed",
            "message": "ffmpeg missing",
            "agentId": agent.agent_id,
            "projectId": str(project_id),
            "observedAt": now.isoformat(),
            "count": 1,
        }
    ]
    filtered_resp = client.get(
        "/api/system/relay-monitor?diagnosticSinceHours=168&diagnosticLimit=5&diagnosticLevel=warning"
        "&diagnosticCategory=manifest&diagnosticQuery=archive"
    )
    assert filtered_resp.status_code == 200
    filtered_body = filtered_resp.json()["data"]
    assert filtered_body["diagnosticSummary"] == {
        "eventCount": 1,
        "errorCount": 0,
        "warningCount": 1,
        "eventsByCategory": {"manifest": 1},
        "eventsByLevel": {"WARNING": 1},
        "eventsByType": {"manifest_sync_failed": 1},
    }
    assert filtered_body["recentDiagnostics"] == [
        {
            "eventId": warning_diagnostic_resp.json()["data"]["eventId"],
            "agentId": agent.agent_id,
            "projectId": str(project_id),
            "instanceId": "inst_manifest",
            "relativePath": "archive/index.json",
            "level": "WARNING",
            "category": "manifest",
            "eventType": "manifest_sync_failed",
            "message": "archive path missing",
            "details": {"root": "archive"},
            "createdAt": older_warning_at,
        }
    ]
    assert filtered_body["alerts"] == []
    export_resp = client.get(
        "/api/system/relay-diagnostics/export?diagnosticSinceHours=168&diagnosticLimit=5&diagnosticLevel=warning"
        "&diagnosticCategory=manifest&diagnosticQuery=archive"
    )
    assert export_resp.status_code == 200
    assert "application/x-ndjson" in export_resp.headers["content-type"]
    assert "attachment; filename=" in export_resp.headers["content-disposition"]
    exported_rows = [json.loads(line) for line in export_resp.text.splitlines() if line.strip()]
    assert exported_rows == [
        {
            "eventId": warning_diagnostic_resp.json()["data"]["eventId"],
            "agentId": agent.agent_id,
            "projectId": str(project_id),
            "instanceId": "inst_manifest",
            "relativePath": "archive/index.json",
            "level": "WARNING",
            "category": "manifest",
            "eventType": "manifest_sync_failed",
            "message": "archive path missing",
            "details": {"root": "archive"},
            "createdAt": older_warning_at,
        }
    ]
    assert body["trends"]["sampleBucketSeconds"] == 300
    assert body["trends"]["retentionDays"] == 30
    assert body["trends"]["sampledProjectCount"] == 1
    assert body["trends"]["sampleCount"] >= 5
    assert body["trends"]["latestCapturedAt"] is not None
    assert body["trends"]["historyStartAt"] is not None
    assert body["trends"]["windows"]["last6Hours"] == {
        "pointCount": 3,
        "uploadBytes": 5632,
        "viewerBytes": 4608,
        "artifactBytes": 0,
        "completedStreams": 1,
        "failedStreams": 1,
        "cancelledStreams": 1,
        "completedHlsJobs": 0,
        "failedHlsJobs": 1,
        "cancelledHlsJobs": 0,
        "peakActiveStreams": 0,
        "peakActiveHlsJobs": 0,
        "peakCacheBytes": 0,
        "latestCacheBytes": 0,
    }
    assert body["trends"]["windows"]["lastDay"] == body["trends"]["windows"]["last6Hours"]
    assert body["trends"]["windows"]["last7Days"] == {
        "pointCount": 4,
        "uploadBytes": 5888,
        "viewerBytes": 4608,
        "artifactBytes": 0,
        "completedStreams": 1,
        "failedStreams": 1,
        "cancelledStreams": 1,
        "completedHlsJobs": 0,
        "failedHlsJobs": 1,
        "cancelledHlsJobs": 0,
        "peakActiveStreams": 0,
        "peakActiveHlsJobs": 0,
        "peakCacheBytes": 0,
        "latestCacheBytes": 0,
    }
    assert body["trends"]["windows"]["last30Days"]["uploadBytes"] == 6400
    assert body["trends"]["windows"]["last30Days"]["viewerBytes"] == 4992
    assert body["trends"]["windows"]["last30Days"]["artifactBytes"] == 0
    assert body["trends"]["windows"]["last30Days"]["completedStreams"] == 1
    assert body["trends"]["windows"]["last30Days"]["failedStreams"] == 1
    assert body["trends"]["windows"]["last30Days"]["cancelledStreams"] == 1
    assert body["trends"]["windows"]["last30Days"]["completedHlsJobs"] == 0
    assert body["trends"]["windows"]["last30Days"]["failedHlsJobs"] == 1
    assert body["trends"]["windows"]["last30Days"]["cancelledHlsJobs"] == 0
    assert body["trends"]["windows"]["last30Days"]["peakActiveStreams"] == 0
    assert body["trends"]["windows"]["last30Days"]["peakActiveHlsJobs"] == 0
    assert body["trends"]["windows"]["last30Days"]["peakCacheBytes"] == 0
    assert body["trends"]["windows"]["last30Days"]["latestCacheBytes"] == 0
    assert len(body["trends"]["timelines"]["last7Days"]) == 4
    assert body["trends"]["windows"]["last30Days"]["pointCount"] >= 3
    assert len(body["trends"]["timelines"]["last30Days"]) == body["trends"]["windows"]["last30Days"]["pointCount"]
    assert [item["uploadBytes"] for item in body["trends"]["timelines"]["last6Hours"]] == [0, 5632, 0]
    assert [item["viewerBytes"] for item in body["trends"]["timelines"]["last6Hours"]] == [0, 4608, 0]
    assert [item["failedHlsJobs"] for item in body["trends"]["timelines"]["last6Hours"]] == [0, 1, 0]
    assert [item["uploadBytes"] for item in body["trends"]["timelines"]["last7Days"]] == [0, 256, 5632, 0]
    assert sum(item["uploadBytes"] for item in body["trends"]["timelines"]["last30Days"]) == 6400
    assert sum(item["viewerBytes"] for item in body["trends"]["timelines"]["last30Days"]) == 4992
    assert max(item["uploadBytes"] for item in body["trends"]["timelines"]["last30Days"]) == 5888


def test_relay_monitor_suppresses_diagnostics_from_non_bound_agent(monkeypatch, tmp_path: Path) -> None:
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
    register_resp = client.post("/api/auth/register", json={"email": "binding@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    create_project_resp = client.post("/api/projects", json={"title": "Binding Monitor"})
    assert create_project_resp.status_code == 200
    project_id = create_project_resp.json()["data"]["projectId"]

    first_pairing = client.post("/api/desktop-agents/pairing-codes")
    assert first_pairing.status_code == 200
    first_pair = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": first_pairing.json()["data"]["pairingCode"],
            "deviceName": "OLD-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert first_pair.status_code == 200
    old_agent = first_pair.json()["data"]

    second_pairing = client.post("/api/desktop-agents/pairing-codes")
    assert second_pairing.status_code == 200
    second_pair = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": second_pairing.json()["data"]["pairingCode"],
            "deviceName": "CURRENT-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert second_pair.status_code == 200
    current_agent = second_pair.json()["data"]

    bind_resp = client.post(
        f"/api/projects/{project_id}/material-source-binding",
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": current_agent["agentId"],
            "sourceRootLabel": "Videos",
        },
    )
    assert bind_resp.status_code == 200

    stale_created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stale_diagnostic = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {old_agent['agentToken']}"},
        json={
            "level": "error",
            "category": "service",
            "eventType": "session_failed",
            "message": "old agent failure",
            "details": {"agentId": old_agent["agentId"]},
            "projectId": str(project_id),
            "createdAt": stale_created_at,
        },
    )
    assert stale_diagnostic.status_code == 200

    current_created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    current_diagnostic = client.post(
        "/api/desktop-agents/diagnostic-events",
        headers={"Authorization": f"Bearer {current_agent['agentToken']}"},
        json={
            "level": "warning",
            "category": "service",
            "eventType": "connected",
            "message": "current agent healthy",
            "details": {"agentId": current_agent["agentId"]},
            "projectId": str(project_id),
            "createdAt": current_created_at,
        },
    )
    assert current_diagnostic.status_code == 200
    current_agent_record = get_auth_store().get_desktop_agent(current_agent["agentId"])

    resp = client.get("/api/system/relay-monitor?diagnosticSinceHours=24&diagnosticLimit=10")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["diagnosticSummary"] == {
        "eventCount": 1,
        "errorCount": 0,
        "warningCount": 1,
        "eventsByCategory": {"service": 1},
        "eventsByLevel": {"WARNING": 1},
        "eventsByType": {"connected": 1},
    }
    assert body["recentDiagnostics"] == [
        {
            "eventId": current_diagnostic.json()["data"]["eventId"],
            "agentId": current_agent["agentId"],
            "projectId": str(project_id),
            "instanceId": None,
            "relativePath": None,
            "level": "WARNING",
            "category": "service",
            "eventType": "connected",
            "message": "current agent healthy",
            "details": {"agentId": current_agent["agentId"]},
            "createdAt": current_created_at,
        }
    ]
    assert body["alerts"] == [
        {
            "severity": "warning",
            "code": "connected",
            "title": "service: connected",
            "message": "current agent healthy",
            "agentId": current_agent["agentId"],
            "projectId": str(project_id),
            "observedAt": current_created_at,
            "count": 1,
        }
    ]
    assert body["projectBindings"] == [
        {
            "projectId": str(project_id),
            "projectTitle": "Binding Monitor",
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": current_agent["agentId"],
            "sourceRootLabel": "Videos",
            "deviceName": "CURRENT-PC",
            "appVersion": "0.1.0",
            "lastSeenAt": current_agent_record.last_seen_at,
            "pairedAt": current_agent_record.paired_at,
            "connected": False,
            "connectionState": "OFFLINE",
            "bindingState": "OFFLINE",
            "supersededByAgentId": None,
        }
    ]


def test_collect_desktop_agent_relay_status_marks_stale_agents_offline(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ALLOW_SIGNUP", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    monkeypatch.setenv("PLM_DESKTOP_AGENT_OFFLINE_GRACE_SECONDS", "30")
    _reset_caches()

    client = TestClient(create_app())
    register_resp = client.post("/api/auth/register", json={"email": "owner@example.com", "password": "password123"})
    assert register_resp.status_code == 200
    pairing_resp = client.post("/api/desktop-agents/pairing-codes")
    assert pairing_resp.status_code == 200
    pair_resp = client.post(
        "/api/desktop-agents/pair",
        json={
            "pairingCode": pairing_resp.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
    )
    assert pair_resp.status_code == 200
    agent_id = pair_resp.json()["data"]["agentId"]
    auth_store = get_auth_store()
    auth_store.update_desktop_agent_presence(
        agent_id,
        status=DesktopAgentStatus.ONLINE,
        last_seen_at="2026-03-11T12:00:00+00:00",
    )

    report = collect_desktop_agent_relay_status(
        runtime=get_desktop_agent_runtime(),
        auth_store=auth_store,
        now=datetime(2026, 3, 11, 12, 1, 0, tzinfo=timezone.utc),
    )

    assert report["staleAgentOfflineCount"] == 1
    assert auth_store.get_desktop_agent(agent_id).status.value == "OFFLINE"


def test_desktop_agent_release_endpoint_exposes_latest_asset_and_download(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    setup_path = release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    setup_path.write_bytes(b"desktop-agent-installer")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-windows-standalone.zip").write_bytes(b"desktop-agent-standalone")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-release.json").write_text(
        json.dumps(
            {
                "version": "0.1.0-beta.1",
                "releaseNotes": "Signed installer release.",
                "assets": {
                    setup_path.name: {
                        "signature": {
                            "status": "SIGNED",
                            "subject": "CN=LearningPyramid",
                            "thumbprint": "ABC123",
                            "signedAt": "2026-03-11T12:00:00+00:00",
                            "source": "signtool",
                        },
                        "silentInstall": {
                            "supported": True,
                            "strategy": "inno_exe",
                            "relaunch": True,
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLM_DESKTOP_AGENT_RELEASE_DIR", str(release_dir))
    _reset_caches()

    client = TestClient(create_app())

    release_resp = client.get("/api/system/desktop-agent-release", params={"currentVersion": "0.1.0-beta.0"})

    assert release_resp.status_code == 200
    body = release_resp.json()["data"]
    assert body["available"] is True
    assert body["updateAvailable"] is True
    assert body["policy"] == {
        "requireSigned": False,
        "acceptedSignatureStatuses": [],
        "rejectedAssetCount": 0,
        "visibleAssetCount": 2,
        "totalAssetCount": 2,
    }
    assert body["latest"]["version"] == "0.1.0-beta.1"
    assert body["latest"]["releaseNotes"] == "Signed installer release."
    assert body["latest"]["preferredAsset"]["kind"] == "installer_exe"
    assert body["latest"]["preferredAsset"]["signature"]["status"] == "SIGNED"
    assert body["latest"]["preferredAsset"]["silentInstall"]["supported"] is True
    assert body["latest"]["preferredAsset"]["downloadPath"].endswith(
        "/api/system/desktop-agent-release/assets/LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    )

    download_resp = client.get(body["latest"]["preferredAsset"]["downloadPath"])

    assert download_resp.status_code == 200
    assert download_resp.content == b"desktop-agent-installer"
    assert "attachment" in download_resp.headers.get("content-disposition", "").lower()
    assert download_resp.headers["x-checksum-sha256"]
    assert download_resp.headers["x-integrity-mode"] == "sha256"
    assert download_resp.headers["x-signature-status"] == "SIGNED"
    assert download_resp.headers["x-silent-install-supported"] == "true"


def test_desktop_agent_release_endpoint_honors_signed_only_policy(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_AUTH", "true")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_DESKTOP_AGENT_RELEASE_REQUIRE_SIGNED", "true")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    release_dir = tmp_path / "release"
    release_dir.mkdir()
    setup_path = release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-Setup.exe"
    setup_path.write_bytes(b"desktop-agent-installer")
    unsigned_zip_path = release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-windows-standalone.zip"
    unsigned_zip_path.write_bytes(b"desktop-agent-standalone")
    (release_dir / "LearningPyramidDesktopAgent-0.1.0-beta.1-release.json").write_text(
        json.dumps(
            {
                "version": "0.1.0-beta.1",
                "releaseNotes": "Signed installer release.",
                "assets": {
                    setup_path.name: {
                        "signature": {
                            "status": "SIGNED",
                            "subject": "CN=LearningPyramid",
                            "thumbprint": "ABC123",
                            "signedAt": "2026-03-11T12:00:00+00:00",
                            "source": "signtool",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PLM_DESKTOP_AGENT_RELEASE_DIR", str(release_dir))
    _reset_caches()

    client = TestClient(create_app())

    release_resp = client.get("/api/system/desktop-agent-release", params={"currentVersion": "0.1.0-beta.0"})

    assert release_resp.status_code == 200
    body = release_resp.json()["data"]
    assert body["available"] is True
    assert body["policy"] == {
        "requireSigned": True,
        "acceptedSignatureStatuses": ["SIGNED"],
        "rejectedAssetCount": 1,
        "visibleAssetCount": 1,
        "totalAssetCount": 2,
    }
    assert body["latest"]["assetCount"] == 1
    assert [item["name"] for item in body["latest"]["assets"]] == [setup_path.name]

    allowed_download_resp = client.get(f"/api/system/desktop-agent-release/assets/{setup_path.name}")
    blocked_download_resp = client.get(f"/api/system/desktop-agent-release/assets/{unsigned_zip_path.name}")

    assert allowed_download_resp.status_code == 200
    assert blocked_download_resp.status_code == 404


def test_background_janitor_finalizes_expired_stream_sessions_without_runtime_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    with TestClient(create_app()):
        project_id = get_api().create_project("Background Janitor", project_root=str(tmp_path / "project-janitor"))
        auth_store = get_auth_store()
        user = auth_store.create_user("janitor@example.com", "password123")
        auth_store.add_project_owner(str(project_id), user.user_id)
        pairing = auth_store.create_desktop_agent_pairing_code(user.user_id)
        agent, _, _ = auth_store.pair_desktop_agent(
            pairing.pairing_code,
            device_name="BYLOU-PC",
            platform="windows",
            app_version="0.1.0",
        )

        runtime = get_desktop_agent_runtime()
        runtime.register_connection(agent.agent_id, object())  # type: ignore[arg-type]
        session = runtime.create_stream_session(
            agent_id=agent.agent_id,
            user_id=user.user_id,
            project_id=str(project_id),
            instance_id="inst_123",
            relative_path="lesson-01.mp4",
            content_type="video/mp4",
            ttl_seconds=120,
        )
        expired_at = (datetime.now(timezone.utc) - timedelta(seconds=1)).replace(microsecond=0).isoformat()
        runtime.get_stream_session(session.stream_id).expires_at = expired_at
        auth_store.create_media_stream_session(
            MediaStreamSession(
                stream_id=session.stream_id,
                project_id=str(project_id),
                instance_id="inst_123",
                agent_id=agent.agent_id,
                user_id=user.user_id,
                mode="relay_progressive",
                status="OPENING",
                range_start=None,
                range_end=None,
                bytes_from_agent=0,
                bytes_to_viewer=0,
                created_at=session.created_at,
                updated_at=session.created_at,
                expires_at=expired_at,
            )
        )

        deadline = time.time() + 2.0
        while time.time() < deadline:
            persisted = auth_store.get_media_stream_session(session.stream_id)
            if persisted.status == "FAILED":
                break
            time.sleep(0.05)
        else:
            pytest.fail("background janitor did not finalize the expired media stream session")

        persisted = auth_store.get_media_stream_session(session.stream_id)
        assert persisted.status == "FAILED"
        assert persisted.finished_at is not None
        assert persisted.failure_reason == "desktop agent stream session expired"

        drained = runtime.drain_commands(agent.agent_id)
        assert drained == [
            {
                "type": "stream.cancel",
                "streamId": session.stream_id,
                "reason": "desktop agent stream session expired",
            }
        ]


def test_background_janitor_persists_metric_samples_without_monitor_request(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PLM_APP_MODE", "hosted")
    monkeypatch.setenv("PLM_ENABLE_ASR", "false")
    monkeypatch.setenv("PLM_ENABLE_SERVER_MEDIA_STREAM", "false")
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0.05")
    monkeypatch.setenv("PLM_AGENT_METRIC_SAMPLE_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    _reset_caches()

    with TestClient(create_app()):
        project_id = get_api().create_project("Trend Samples", project_root=str(tmp_path / "project-trends"))
        auth_store = get_auth_store()
        user = auth_store.create_user("trend@example.com", "password123")
        auth_store.add_project_owner(str(project_id), user.user_id)
        pairing = auth_store.create_desktop_agent_pairing_code(user.user_id)
        agent, _, _ = auth_store.pair_desktop_agent(
            pairing.pairing_code,
            device_name="BYLOU-PC",
            platform="windows",
            app_version="0.1.0",
        )
        auth_store.create_media_stream_session(
            MediaStreamSession(
                stream_id="stream_trend",
                project_id=str(project_id),
                instance_id="inst_123",
                agent_id=agent.agent_id,
                user_id=user.user_id,
                mode="relay_progressive",
                status="COMPLETED",
                range_start=0,
                range_end=127,
                bytes_from_agent=2048,
                bytes_to_viewer=2048,
                created_at="2026-03-11T12:00:00+00:00",
                updated_at="2026-03-11T12:01:00+00:00",
                expires_at="2026-03-11T13:00:00+00:00",
                finished_at="2026-03-11T12:01:00+00:00",
            )
        )

        deadline = time.time() + 2.0
        while time.time() < deadline:
            samples = auth_store.list_desktop_agent_metric_samples_for_project(str(project_id))
            if samples:
                break
            time.sleep(0.05)
        else:
            pytest.fail("background janitor did not persist desktop agent metric samples")

        sample = auth_store.list_desktop_agent_metric_samples_for_project(str(project_id))[-1]
        assert sample.bucket_seconds == 1
        assert sample.session_count == 1
        assert sample.completed_stream_count == 1
        assert sample.bytes_from_agent_total == 2048
        assert sample.bytes_to_viewer_total == 2048


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
