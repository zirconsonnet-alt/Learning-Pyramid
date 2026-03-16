from __future__ import annotations

import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable
from urllib.parse import urljoin

import pytest
import requests
import uvicorn

from adapter.desktop_agent_alert_webhooks import reset_desktop_agent_alert_webhook_dispatcher
from adapter.desktop_agent_janitor import collect_desktop_agent_relay_status
from adapter.deps import get_api, get_auth_store, get_desktop_agent_runtime
from adapter.main import create_app
from desktop_agent.config_store import AgentConfig, ConfigStore
from desktop_agent.relay_client import RelayClient
from desktop_agent.service import DesktopAgentService


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
    monkeypatch.setenv("PLM_AGENT_JANITOR_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("PLM_PROJECTS_ROOT", str(tmp_path / "projects"))
    monkeypatch.setenv("PLM_STORE_PATH", "")
    monkeypatch.setenv("PLM_LEGACY_STORE_PATH", "")
    monkeypatch.setenv("PLM_STORE_DB_PATH", str(tmp_path / "plm_store.sqlite3"))
    monkeypatch.setenv("PLM_AUTH_DB_PATH", str(tmp_path / "plm_auth.sqlite3"))
    reset_desktop_agent_alert_webhook_dispatcher()
    _reset_caches()
    yield
    reset_desktop_agent_alert_webhook_dispatcher()
    _reset_caches()


def _wait_until(
    predicate: Callable[[], bool],
    *,
    timeout_seconds: float = 8.0,
    interval_seconds: float = 0.05,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval_seconds)
    raise AssertionError("condition not satisfied before timeout")


def _reserve_free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _LocalApiServer:
    def __init__(self, *, port: int) -> None:
        self.port = int(port)
        self._server = uvicorn.Server(
            uvicorn.Config(
                create_app(),
                host="127.0.0.1",
                port=self.port,
                log_level="error",
                access_log=False,
            )
        )
        self._thread = Thread(target=self._server.run, name=f"api-server-{self.port}", daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        self._thread.start()
        _wait_until(lambda: bool(self._server.started), timeout_seconds=10.0)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10.0)
        if self._thread.is_alive():
            raise AssertionError(f"api server on port {self.port} did not stop in time")


def _run_service_in_thread(
    service: DesktopAgentService,
    *,
    stop_event: Event,
    statuses: list[tuple[str, str | None]],
) -> tuple[Thread, dict[str, BaseException]]:
    holder: dict[str, BaseException] = {}

    def _target() -> None:
        try:
            service.run_forever(
                stop_event=stop_event,
                status_callback=lambda state, message: statuses.append((state, message)),
            )
        except BaseException as exc:  # pragma: no cover - surfaced via assertion
            holder["exception"] = exc

    thread = Thread(target=_target, name="desktop-agent-service-api-test", daemon=True)
    thread.start()
    return thread, holder


def _join_service_thread(thread: Thread, holder: dict[str, BaseException], *, timeout_seconds: float = 12.0) -> None:
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise AssertionError("desktop agent service thread did not stop in time")
    if "exception" in holder:
        raise holder["exception"]


def _api_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _register_user(session: requests.Session, base_url: str, *, email: str, password: str = "password123") -> None:
    response = session.post(
        _api_url(base_url, "/api/auth/register"),
        json={"email": email, "password": password},
        timeout=10,
    )
    assert response.status_code == 200, response.text


def _login_user(session: requests.Session, base_url: str, *, email: str, password: str = "password123") -> None:
    response = session.post(
        _api_url(base_url, "/api/auth/login"),
        json={"email": email, "password": password},
        timeout=10,
    )
    assert response.status_code == 200, response.text


def _create_project(session: requests.Session, base_url: str, *, title: str = "Hosted Project") -> str:
    response = session.post(
        _api_url(base_url, "/api/projects"),
        json={"title": title},
        timeout=10,
    )
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["projectId"])


def _pair_desktop_agent(session: requests.Session, base_url: str) -> dict[str, str]:
    pairing = session.post(_api_url(base_url, "/api/desktop-agents/pairing-codes"), timeout=10)
    assert pairing.status_code == 200, pairing.text
    paired = session.post(
        _api_url(base_url, "/api/desktop-agents/pair"),
        json={
            "pairingCode": pairing.json()["data"]["pairingCode"],
            "deviceName": "BYLOU-PC",
            "platform": "windows",
            "appVersion": "0.1.0",
        },
        timeout=10,
    )
    assert paired.status_code == 200, paired.text
    return dict(paired.json()["data"])


def _bind_project_to_agent(
    session: requests.Session,
    base_url: str,
    *,
    project_id: str,
    agent_id: str,
    source_root_label: str = "Videos",
) -> None:
    response = session.post(
        _api_url(base_url, f"/api/projects/{project_id}/material-source-binding"),
        json={
            "sourceKind": "DESKTOP_AGENT_MANIFEST",
            "desktopAgentId": agent_id,
            "sourceRootLabel": source_root_label,
        },
        timeout=10,
    )
    assert response.status_code == 200, response.text


def _seed_service_config(
    tmp_path: Path,
    *,
    base_url: str,
    pair_data: dict[str, str],
    project_id: str,
    media_root: Path,
    source_root_label: str = "Videos",
) -> ConfigStore:
    store = ConfigStore(tmp_path / "agent-config")
    store.save(
        AgentConfig(
            server_url=base_url,
            agent_id=str(pair_data["agentId"]),
            agent_token=str(pair_data["agentToken"]),
            refresh_token=str(pair_data["refreshToken"]),
            project_id=str(project_id),
            root_dir=str(media_root),
            device_name="BYLOU-PC",
            source_root_label=source_root_label,
        )
    )
    return store


def _wait_for_instance_id(session: requests.Session, base_url: str, *, project_id: str) -> str:
    holder: dict[str, str] = {}

    def _has_instance() -> bool:
        response = session.get(_api_url(base_url, f"/api/projects/{project_id}/instances"), timeout=10)
        if response.status_code != 200:
            return False
        items = list(response.json()["data"])
        if not items:
            return False
        holder["instance_id"] = str(items[0]["instanceId"])
        return True

    _wait_until(_has_instance, timeout_seconds=10.0)
    return holder["instance_id"]


def _project_agent_status(session: requests.Session, base_url: str, *, project_id: str) -> dict:
    response = session.get(_api_url(base_url, f"/api/projects/{project_id}/desktop-agents/status"), timeout=10)
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def _relay_monitor(session: requests.Session, base_url: str) -> dict:
    response = session.get(_api_url(base_url, "/api/system/relay-monitor"), timeout=10)
    assert response.status_code == 200, response.text
    return dict(response.json()["data"])


def _stream_session_for_project(project_id: str):
    sessions = get_auth_store().list_media_stream_sessions_for_project(project_id)
    return sessions[0] if sessions else None


def _hls_job_audit_for_project(project_id: str):
    jobs = get_auth_store().list_desktop_agent_hls_job_audits_for_project(project_id)
    return jobs[0] if jobs else None


def _diagnostic_event_types(monitor_payload: dict) -> dict[str, int]:
    summary = dict(monitor_payload.get("diagnosticSummary") or {})
    return {
        str(key): int(value)
        for key, value in dict(summary.get("eventsByType") or {}).items()
    }


def _alert_codes(monitor_payload: dict) -> set[str]:
    return {
        str(item.get("code", "")).strip()
        for item in list(monitor_payload.get("alerts") or [])
        if str(item.get("code", "")).strip()
    }


class _WebhookResponse:
    def raise_for_status(self) -> None:
        return None


def test_progressive_relay_api_reports_reconnecting_while_stream_continues_over_http(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    media_root = tmp_path / "media-root"
    media_root.mkdir(parents=True, exist_ok=True)
    media_file = media_root / "lesson-01.mp4"
    media_file.write_bytes(b"abcdefghij")

    port = _reserve_free_port()
    server = _LocalApiServer(port=port)
    server.start()

    owner_session = requests.Session()
    browser_session = requests.Session()
    owner_session.trust_env = False
    browser_session.trust_env = False

    stop_event = Event()
    statuses: list[tuple[str, str | None]] = []
    ws_connections: list[object] = []
    ws_lock = Lock()
    first_chunk_uploaded = Event()
    webhook_calls: list[dict[str, object]] = []

    monkeypatch.setenv("PLM_AGENT_METRIC_SAMPLE_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("PLM_AGENT_ALERT_WEBHOOK_URL", "https://example.com/hooks/progressive-recovery")
    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: str(tmp_path / f"{name}.exe"))
    monkeypatch.setattr(
        "desktop_agent.relay_client.probe_media_file",
        lambda *_args, **_kwargs: {
            "container": "mp4",
            "videoCodec": "h264",
            "audioCodec": "aac",
            "durationMs": 60_000,
            "bitrateBps": 1_500_000,
            "width": 1280,
            "height": 720,
            "fps": 24.0,
            "audioChannels": 2,
            "audioSampleRate": 48_000,
            "videoStreamCount": 1,
            "audioStreamCount": 1,
            "subtitleStreamCount": 0,
            "sizeBytes": len(media_file.read_bytes()),
            "modifiedAt": "2026-03-11T12:00:00+00:00",
        },
    )

    original_create_connection = RelayClient.run_session.__globals__["websocket"].create_connection

    def _instrumented_create_connection(*args, **kwargs):
        ws = original_create_connection(*args, **kwargs)
        with ws_lock:
            ws_connections.append(ws)
        return ws

    monkeypatch.setattr("desktop_agent.relay_client.websocket.create_connection", _instrumented_create_connection)

    original_upload_stream_chunk = RelayClient._upload_stream_chunk

    def _instrumented_upload_stream_chunk(self, **kwargs):
        result = original_upload_stream_chunk(self, **kwargs)
        first_chunk_uploaded.set()
        time.sleep(0.15)
        return result

    def _fake_post(url: str, *, json: object, timeout: float):
        webhook_calls.append({"url": url, "json": json, "timeout": timeout})
        return _WebhookResponse()

    reset_desktop_agent_alert_webhook_dispatcher(_fake_post)
    monkeypatch.setattr(RelayClient, "_upload_stream_chunk", _instrumented_upload_stream_chunk)

    try:
        _register_user(owner_session, server.base_url, email="owner@example.com")
        _login_user(browser_session, server.base_url, email="owner@example.com")
        project_id = _create_project(owner_session, server.base_url, title="Progressive Recovery")
        pair_data = _pair_desktop_agent(owner_session, server.base_url)
        _bind_project_to_agent(
            owner_session,
            server.base_url,
            project_id=project_id,
            agent_id=str(pair_data["agentId"]),
        )

        store = _seed_service_config(
            tmp_path,
            base_url=server.base_url,
            pair_data=pair_data,
            project_id=project_id,
            media_root=media_root,
        )
        service = DesktopAgentService(
            config_store=store,
            client_factory=lambda config: RelayClient(config, stream_chunk_size_bytes=2),
            reconnect_delay_seconds=0.4,
            refresh_interval_seconds=60,
            sleep_fn=time.sleep,
        )
        thread, holder = _run_service_in_thread(service, stop_event=stop_event, statuses=statuses)

        try:
            instance_id = _wait_for_instance_id(owner_session, server.base_url, project_id=project_id)
            _wait_until(
                lambda: _project_agent_status(owner_session, server.base_url, project_id=project_id)["agent"]["connected"] is True,
                timeout_seconds=10.0,
            )

            descriptor = owner_session.get(
                _api_url(server.base_url, f"/api/projects/{project_id}/media/instances/{instance_id}/playback"),
                timeout=10,
            )
            assert descriptor.status_code == 200, descriptor.text
            descriptor_data = descriptor.json()["data"]
            assert descriptor_data["mode"] == "relay_progressive"

            result_holder: dict[str, object] = {}

            def _fetch_media() -> None:
                result_holder["response"] = browser_session.get(
                    urljoin(server.base_url, str(descriptor_data["url"])),
                    headers={"Range": "bytes=0-9"},
                    timeout=10,
                )

            worker = Thread(target=_fetch_media, name="progressive-browser-fetch", daemon=True)
            worker.start()

            _wait_until(first_chunk_uploaded.is_set, timeout_seconds=10.0)
            _wait_until(lambda: _stream_session_for_project(project_id) is not None, timeout_seconds=10.0)
            persisted_before_disconnect = _stream_session_for_project(project_id)
            assert persisted_before_disconnect is not None
            assert persisted_before_disconnect.status == "STREAMING"

            with ws_lock:
                assert ws_connections
                first_ws = ws_connections[0]
            first_ws.close()

            _wait_until(
                lambda: any(state_name == "ERROR" for state_name, _ in statuses),
                timeout_seconds=10.0,
            )
            _wait_until(
                lambda: _project_agent_status(owner_session, server.base_url, project_id=project_id)["agent"]["connectionState"]
                == "RECONNECTING",
                timeout_seconds=10.0,
            )

            monitor_during_disconnect = _relay_monitor(owner_session, server.base_url)
            assert monitor_during_disconnect["agents"][0]["connected"] is False
            assert monitor_during_disconnect["agents"][0]["connectionState"] == "RECONNECTING"
            assert monitor_during_disconnect["agents"][0]["activeStreamCount"] == 1
            assert monitor_during_disconnect["streamSummary"]["activeSessionCount"] == 1
            assert monitor_during_disconnect["streamSummary"]["failedSessionCount"] == 0
            assert monitor_during_disconnect["streamSummary"]["issueReasonCounts"] == {}
            assert monitor_during_disconnect["recentIssues"] == []
            assert _diagnostic_event_types(monitor_during_disconnect).get("connection_lost", 0) >= 1
            assert _diagnostic_event_types(monitor_during_disconnect).get("session_failed", 0) >= 1

            bytes_after_first_chunk = int(persisted_before_disconnect.bytes_from_agent)
            _wait_until(
                lambda: (
                    _stream_session_for_project(project_id) is not None
                    and int(_stream_session_for_project(project_id).bytes_from_agent) > bytes_after_first_chunk
                ),
                timeout_seconds=10.0,
            )
            assert _stream_session_for_project(project_id) is not None
            assert _stream_session_for_project(project_id).status == "STREAMING"

            _wait_until(lambda: len(ws_connections) >= 2, timeout_seconds=10.0)
            _wait_until(
                lambda: _project_agent_status(owner_session, server.base_url, project_id=project_id)["agent"]["connected"] is True,
                timeout_seconds=10.0,
            )

            worker.join(timeout=10.0)
            if worker.is_alive():
                raise AssertionError("progressive browser fetch did not finish in time")

            response = result_holder["response"]
            assert isinstance(response, requests.Response)
            assert response.status_code == 206
            assert response.content == b"abcdefghij"
            assert response.headers["Content-Range"] == "bytes 0-9/10"

            _wait_until(
                lambda: (
                    _stream_session_for_project(project_id) is not None
                    and _stream_session_for_project(project_id).status == "COMPLETED"
                ),
                timeout_seconds=10.0,
            )
            completed = _stream_session_for_project(project_id)
            assert completed is not None
            assert completed.status == "COMPLETED"
            assert completed.failure_reason is None
            assert completed.bytes_from_agent == 10
            assert completed.bytes_to_viewer == 10

            time.sleep(1.1)
            completed_monitor = _relay_monitor(owner_session, server.base_url)
            assert completed_monitor["agents"][0]["connected"] is True
            assert completed_monitor["agents"][0]["connectionState"] == "CONNECTED"
            assert completed_monitor["streamSummary"]["activeSessionCount"] == 0
            assert completed_monitor["streamSummary"]["completedSessionCount"] == 1
            assert completed_monitor["streamSummary"]["failedSessionCount"] == 0
            assert completed_monitor["streamSummary"]["issueReasonCounts"] == {}
            assert completed_monitor["recentIssues"] == []
            assert {"session_failed", "connection_lost"} <= _alert_codes(completed_monitor)
            assert "stream_failed" not in _alert_codes(completed_monitor)
            assert "stream_open_failed" not in _alert_codes(completed_monitor)
            completed_event_types = _diagnostic_event_types(completed_monitor)
            assert completed_event_types.get("stream_opened", 0) >= 1
            assert completed_event_types.get("stream_completed", 0) >= 1
            assert completed_event_types.get("connection_lost", 0) >= 1
            assert completed_event_types.get("session_failed", 0) >= 1
            progressive_trends = dict(completed_monitor["trends"]["windows"]["last6Hours"])
            assert progressive_trends["pointCount"] >= 2
            assert progressive_trends["uploadBytes"] > 0
            assert progressive_trends["viewerBytes"] > 0
            assert progressive_trends["completedStreams"] == 1
            assert progressive_trends["failedStreams"] == 0
            assert progressive_trends["cancelledStreams"] == 0
            assert progressive_trends["completedHlsJobs"] == 0
            assert progressive_trends["failedHlsJobs"] == 0
            assert progressive_trends["cancelledHlsJobs"] == 0
            assert progressive_trends["peakActiveStreams"] >= 1
            assert progressive_trends["peakActiveHlsJobs"] == 0
            assert progressive_trends["latestCacheBytes"] == 0

            webhook_observed_at = datetime.now(timezone.utc).replace(microsecond=0)
            webhook_report = collect_desktop_agent_relay_status(
                runtime=get_desktop_agent_runtime(),
                auth_store=get_auth_store(),
                dispatch_alert_webhooks=True,
                now=webhook_observed_at,
            )
            assert webhook_report["alertWebhook"]["sentCount"] == 0
            assert webhook_report["alertWebhook"]["suppressedCount"] == 0
            assert webhook_report["alertWebhook"]["failedCount"] == 0
            assert webhook_report["alertWebhook"]["lastAlertCount"] == 0
            assert len(webhook_calls) == 0

            suppressed_report = collect_desktop_agent_relay_status(
                runtime=get_desktop_agent_runtime(),
                auth_store=get_auth_store(),
                dispatch_alert_webhooks=True,
                now=webhook_observed_at + timedelta(seconds=30),
            )
            assert suppressed_report["alertWebhook"]["sentCount"] == 0
            assert suppressed_report["alertWebhook"]["suppressedCount"] == 0
            assert suppressed_report["alertWebhook"]["failedCount"] == 0
            assert suppressed_report["alertWebhook"]["lastAlertCount"] == 0
            assert len(webhook_calls) == 0

            state_names = [state_name for state_name, _ in statuses]
            assert state_names.count("RUNNING") >= 2
            assert "ERROR" in state_names
        finally:
            stop_event.set()
            _join_service_thread(thread, holder)
    finally:
        owner_session.close()
        browser_session.close()
        server.stop()


def test_hls_api_reports_reconnecting_while_http_artifacts_continue_until_ready(
    auth_env: None,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    media_root = tmp_path / "media-root"
    media_root.mkdir(parents=True, exist_ok=True)
    media_file = media_root / "lesson-02.mkv"
    media_file.write_bytes(b"fake-mkv-payload")

    port = _reserve_free_port()
    server = _LocalApiServer(port=port)
    server.start()

    owner_session = requests.Session()
    owner_session.trust_env = False

    stop_event = Event()
    statuses: list[tuple[str, str | None]] = []
    ws_connections: list[object] = []
    ws_lock = Lock()
    first_artifact_uploaded = Event()
    webhook_calls: list[dict[str, object]] = []

    monkeypatch.setenv("PLM_AGENT_METRIC_SAMPLE_INTERVAL_SECONDS", "1")
    monkeypatch.setenv("PLM_AGENT_ALERT_WEBHOOK_URL", "https://example.com/hooks/hls-recovery")
    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: str(tmp_path / f"{name}.exe"))
    monkeypatch.setattr(
        "desktop_agent.relay_client.probe_media_file",
        lambda *_args, **_kwargs: {
            "container": "mkv",
            "videoCodec": "hevc",
            "audioCodec": "aac",
            "durationMs": 60_000,
            "bitrateBps": 6_000_000,
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "audioChannels": 2,
            "audioSampleRate": 48_000,
            "videoStreamCount": 1,
            "audioStreamCount": 1,
            "subtitleStreamCount": 0,
            "sizeBytes": len(media_file.read_bytes()),
            "modifiedAt": "2026-03-11T12:00:00+00:00",
        },
    )

    def _fake_transcode(_root_dir, _relative_path, **_kwargs):
        output_dir = Path(tempfile.mkdtemp(dir=str(tmp_path)))
        playlist = output_dir / "index.m3u8"
        playlist.write_bytes(b"#EXTM3U\n#EXTINF:6.0,\nsegment000.ts\n#EXT-X-ENDLIST\n")
        segment = output_dir / "segment000.ts"
        segment.write_bytes(b"fake-ts-segment")
        master = output_dir / "master.m3u8"
        master.write_bytes(b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=2000000\nindex.m3u8\n")
        return output_dir, [playlist, segment, master]

    monkeypatch.setattr("desktop_agent.relay_client.transcode_media_to_hls", _fake_transcode)

    original_create_connection = RelayClient.run_session.__globals__["websocket"].create_connection

    def _instrumented_create_connection(*args, **kwargs):
        ws = original_create_connection(*args, **kwargs)
        with ws_lock:
            ws_connections.append(ws)
        return ws

    monkeypatch.setattr("desktop_agent.relay_client.websocket.create_connection", _instrumented_create_connection)

    original_upload_hls_artifact = RelayClient._upload_hls_artifact

    def _instrumented_upload_hls_artifact(self, **kwargs):
        result = original_upload_hls_artifact(self, **kwargs)
        first_artifact_uploaded.set()
        time.sleep(0.2)
        return result

    def _fake_post(url: str, *, json: object, timeout: float):
        webhook_calls.append({"url": url, "json": json, "timeout": timeout})
        return _WebhookResponse()

    reset_desktop_agent_alert_webhook_dispatcher(_fake_post)
    monkeypatch.setattr(RelayClient, "_upload_hls_artifact", _instrumented_upload_hls_artifact)

    try:
        _register_user(owner_session, server.base_url, email="owner@example.com")
        project_id = _create_project(owner_session, server.base_url, title="HLS Recovery")
        pair_data = _pair_desktop_agent(owner_session, server.base_url)
        _bind_project_to_agent(
            owner_session,
            server.base_url,
            project_id=project_id,
            agent_id=str(pair_data["agentId"]),
        )

        store = _seed_service_config(
            tmp_path,
            base_url=server.base_url,
            pair_data=pair_data,
            project_id=project_id,
            media_root=media_root,
        )
        service = DesktopAgentService(
            config_store=store,
            client_factory=lambda config: RelayClient(config, stream_chunk_size_bytes=2),
            reconnect_delay_seconds=0.4,
            refresh_interval_seconds=60,
            sleep_fn=time.sleep,
        )
        thread, holder = _run_service_in_thread(service, stop_event=stop_event, statuses=statuses)

        try:
            instance_id = _wait_for_instance_id(owner_session, server.base_url, project_id=project_id)
            _wait_until(
                lambda: _project_agent_status(owner_session, server.base_url, project_id=project_id)["agent"]["connected"] is True,
                timeout_seconds=10.0,
            )

            descriptor = owner_session.get(
                _api_url(
                    server.base_url,
                    f"/api/projects/{project_id}/media/instances/{instance_id}/playback?preferHls=true",
                ),
                timeout=10,
            )
            assert descriptor.status_code == 200, descriptor.text
            descriptor_data = descriptor.json()["data"]
            assert descriptor_data["mode"] == "relay_hls"
            assert descriptor_data["ready"] is False
            assert descriptor_data["reason"] == "transcode_pending"

            _wait_until(first_artifact_uploaded.is_set, timeout_seconds=10.0)
            _wait_until(lambda: _hls_job_audit_for_project(project_id) is not None, timeout_seconds=10.0)
            audit_before_disconnect = _hls_job_audit_for_project(project_id)
            assert audit_before_disconnect is not None
            assert audit_before_disconnect.state == "RUNNING"

            with ws_lock:
                assert ws_connections
                first_ws = ws_connections[0]
            first_ws.close()

            _wait_until(
                lambda: any(state_name == "ERROR" for state_name, _ in statuses),
                timeout_seconds=10.0,
            )
            _wait_until(
                lambda: _project_agent_status(owner_session, server.base_url, project_id=project_id)["agent"]["connectionState"]
                == "RECONNECTING",
                timeout_seconds=10.0,
            )

            monitor_during_disconnect = _relay_monitor(owner_session, server.base_url)
            assert monitor_during_disconnect["agents"][0]["connected"] is False
            assert monitor_during_disconnect["agents"][0]["connectionState"] == "RECONNECTING"
            assert monitor_during_disconnect["agents"][0]["activeHlsJobCount"] == 1
            assert monitor_during_disconnect["hlsSummary"]["activeHlsJobCount"] == 1
            assert monitor_during_disconnect["hlsSummary"]["jobsByState"] == {"RUNNING": 1}
            assert monitor_during_disconnect["hlsSummary"]["issueReasonCounts"] == {}
            assert monitor_during_disconnect["recentHlsJobs"][0]["state"] == "RUNNING"
            assert monitor_during_disconnect["recentHlsJobs"][0]["connectionLostAt"] is not None
            assert _diagnostic_event_types(monitor_during_disconnect).get("connection_lost", 0) >= 1
            assert _diagnostic_event_types(monitor_during_disconnect).get("session_failed", 0) >= 1

            artifact_count_before = int(audit_before_disconnect.artifact_count)
            _wait_until(
                lambda: (
                    _hls_job_audit_for_project(project_id) is not None
                    and int(_hls_job_audit_for_project(project_id).artifact_count) > artifact_count_before
                ),
                timeout_seconds=10.0,
            )

            pending_during_disconnect = owner_session.get(
                _api_url(
                    server.base_url,
                    f"/api/projects/{project_id}/media/instances/{instance_id}/playback?preferHls=true",
                ),
                timeout=10,
            )
            assert pending_during_disconnect.status_code == 200, pending_during_disconnect.text
            pending_data = pending_during_disconnect.json()["data"]
            assert pending_data["mode"] == "relay_hls"
            assert pending_data["ready"] is False
            assert pending_data["reason"] == "transcode_pending"

            _wait_until(lambda: len(ws_connections) >= 2, timeout_seconds=10.0)
            _wait_until(
                lambda: _project_agent_status(owner_session, server.base_url, project_id=project_id)["agent"]["connected"] is True,
                timeout_seconds=10.0,
            )
            _wait_until(
                lambda: (
                    owner_session.get(
                        _api_url(
                            server.base_url,
                            f"/api/projects/{project_id}/media/instances/{instance_id}/playback?preferHls=true",
                        ),
                        timeout=10,
                    ).json()["data"]["ready"]
                    is True
                ),
                timeout_seconds=10.0,
            )

            ready_descriptor = owner_session.get(
                _api_url(
                    server.base_url,
                    f"/api/projects/{project_id}/media/instances/{instance_id}/playback?preferHls=true",
                ),
                timeout=10,
            )
            assert ready_descriptor.status_code == 200, ready_descriptor.text
            ready_data = ready_descriptor.json()["data"]
            assert ready_data["mode"] == "relay_hls"
            assert ready_data["ready"] is True

            manifest = requests.get(urljoin(server.base_url, str(ready_data["manifestUrl"])), timeout=10)
            assert manifest.status_code == 200
            assert "index.m3u8" in manifest.text

            _wait_until(
                lambda: (
                    _hls_job_audit_for_project(project_id) is not None
                    and _hls_job_audit_for_project(project_id).state == "COMPLETED"
                    and int(_hls_job_audit_for_project(project_id).artifact_count) == 3
                ),
                timeout_seconds=10.0,
            )
            completed_audit = _hls_job_audit_for_project(project_id)
            assert completed_audit is not None
            assert completed_audit.state == "COMPLETED"
            assert completed_audit.artifact_count == 3
            assert completed_audit.finished_at is not None

            time.sleep(1.1)
            completed_monitor = _relay_monitor(owner_session, server.base_url)
            assert completed_monitor["agents"][0]["connected"] is True
            assert completed_monitor["agents"][0]["connectionState"] == "CONNECTED"
            assert completed_monitor["hlsSummary"]["activeHlsJobCount"] == 0
            assert completed_monitor["hlsSummary"]["jobsByState"] == {"COMPLETED": 1}
            assert completed_monitor["hlsSummary"]["issueReasonCounts"] == {}
            assert completed_monitor["recentHlsJobs"][0]["state"] == "COMPLETED"
            assert completed_monitor["recentHlsJobs"][0]["artifactCount"] == 3
            assert {"session_failed", "connection_lost"} <= _alert_codes(completed_monitor)
            assert "hls_failed" not in _alert_codes(completed_monitor)
            completed_event_types = _diagnostic_event_types(completed_monitor)
            assert completed_event_types.get("hls_job_requested", 0) >= 1
            assert completed_event_types.get("hls_job_running", 0) >= 1
            assert completed_event_types.get("hls_job_completed", 0) >= 1
            assert completed_event_types.get("hls_manifest_uploaded", 0) >= 2
            assert completed_event_types.get("connection_lost", 0) >= 1
            assert completed_event_types.get("session_failed", 0) >= 1
            hls_trends = dict(completed_monitor["trends"]["windows"]["last6Hours"])
            assert hls_trends["pointCount"] >= 2
            assert hls_trends["artifactBytes"] > 0
            assert hls_trends["completedHlsJobs"] == 1
            assert hls_trends["failedHlsJobs"] == 0
            assert hls_trends["cancelledHlsJobs"] == 0
            assert hls_trends["completedStreams"] == 0
            assert hls_trends["failedStreams"] == 0
            assert hls_trends["cancelledStreams"] == 0
            assert hls_trends["peakActiveHlsJobs"] >= 1
            assert hls_trends["peakActiveStreams"] == 0
            assert hls_trends["peakCacheBytes"] > 0
            assert hls_trends["latestCacheBytes"] > 0

            webhook_observed_at = datetime.now(timezone.utc).replace(microsecond=0)
            webhook_report = collect_desktop_agent_relay_status(
                runtime=get_desktop_agent_runtime(),
                auth_store=get_auth_store(),
                dispatch_alert_webhooks=True,
                now=webhook_observed_at,
            )
            assert webhook_report["alertWebhook"]["sentCount"] == 0
            assert webhook_report["alertWebhook"]["suppressedCount"] == 0
            assert webhook_report["alertWebhook"]["failedCount"] == 0
            assert webhook_report["alertWebhook"]["lastAlertCount"] == 0
            assert len(webhook_calls) == 0

            suppressed_report = collect_desktop_agent_relay_status(
                runtime=get_desktop_agent_runtime(),
                auth_store=get_auth_store(),
                dispatch_alert_webhooks=True,
                now=webhook_observed_at + timedelta(seconds=30),
            )
            assert suppressed_report["alertWebhook"]["sentCount"] == 0
            assert suppressed_report["alertWebhook"]["suppressedCount"] == 0
            assert suppressed_report["alertWebhook"]["failedCount"] == 0
            assert suppressed_report["alertWebhook"]["lastAlertCount"] == 0
            assert len(webhook_calls) == 0

            state_names = [state_name for state_name, _ in statuses]
            assert state_names.count("RUNNING") >= 2
            assert "ERROR" in state_names
        finally:
            stop_event.set()
            _join_service_thread(thread, holder)
    finally:
        owner_session.close()
        server.stop()
