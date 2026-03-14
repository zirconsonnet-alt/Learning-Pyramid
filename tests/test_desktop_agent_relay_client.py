from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Event

import pytest
import requests
import websocket

from desktop_agent.config_store import AgentConfig
from desktop_agent.errors import DesktopAgentTaskCancelled
from desktop_agent.relay_client import DesktopAgentAuthExpired, RelayClient, _raise_for_agent_response


class _FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    def send(self, payload: str) -> None:
        self.sent.append(dict(json.loads(payload)))


def _create_client(root_dir: Path, *, stream_chunk_size_bytes: int = 4) -> RelayClient:
    return RelayClient(
        AgentConfig(
            server_url="http://127.0.0.1:8000",
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(root_dir),
            device_name="BYLOU-PC",
        ),
        stream_chunk_size_bytes=stream_chunk_size_bytes,
    )


def _wait_until(predicate, *, timeout_seconds: float = 2.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not satisfied before timeout")


def _http_error(status_code: int, url: str, message: str) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Not Found" if status_code == 404 else "Conflict"
    response.url = url
    return requests.HTTPError(message, response=response)


def test_relay_client_stream_cancel_stops_before_next_chunk(tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "lesson-01.mp4").write_bytes(b"abcdefghij")
    client = _create_client(media_root, stream_chunk_size_bytes=4)

    uploaded_chunks: list[bytes] = []
    first_chunk_uploaded = Event()
    allow_next_step = Event()

    def _fake_upload_stream_chunk(**kwargs) -> None:
        uploaded_chunks.append(bytes(kwargs["chunk"]))
        if len(uploaded_chunks) == 1:
            first_chunk_uploaded.set()
            allow_next_step.wait(timeout=1)

    client._upload_stream_chunk = _fake_upload_stream_chunk  # type: ignore[method-assign]

    client._handle_stream_open(
        {
            "type": "stream.open",
            "streamId": "stream_123",
            "relativePath": "lesson-01.mp4",
            "contentType": "video/mp4",
            "rangeStart": 0,
            "rangeEnd": 9,
        }
    )
    assert first_chunk_uploaded.wait(timeout=1)

    client._handle_stream_cancel({"type": "stream.cancel", "streamId": "stream_123", "reason": "viewer disconnected"})
    allow_next_step.set()
    _wait_until(lambda: client._active_task_counts()["stream"] == 0)

    assert uploaded_chunks == [b"abcd"]


def test_relay_client_stream_session_not_found_does_not_fail_client(tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "lesson-01.mp4").write_bytes(b"abcdefghij")
    client = _create_client(media_root, stream_chunk_size_bytes=4)

    response = requests.Response()
    response.status_code = 404
    response.reason = "Not Found"
    response.url = "https://plm.xuebao.chat/api/desktop-agents/stream-sessions/stream_123/chunks"
    error = requests.HTTPError(
        "404 Client Error: desktop agent stream session not found: stream_123 for url: https://plm.xuebao.chat/api/desktop-agents/stream-sessions/stream_123/chunks",
        response=response,
    )

    def _fake_upload_stream_chunk(**kwargs) -> None:
        raise error

    client._upload_stream_chunk = _fake_upload_stream_chunk  # type: ignore[method-assign]

    client._handle_stream_open(
        {
            "type": "stream.open",
            "streamId": "stream_123",
            "relativePath": "lesson-01.mp4",
            "contentType": "video/mp4",
            "rangeStart": 0,
            "rangeEnd": 9,
        }
    )

    _wait_until(lambda: client._active_task_counts()["stream"] == 0)
    client._raise_background_error_if_any()


def test_relay_client_hls_job_cancel_reports_cancelled(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    client = _create_client(media_root)
    fake_ws = _FakeWebSocket()
    transcode_started = Event()
    state_updates: list[tuple[str, str, str | None]] = []
    client.report_diagnostic_event = lambda **kwargs: True  # type: ignore[method-assign]
    client._report_hls_job_state_http = (  # type: ignore[method-assign]
        lambda **kwargs: state_updates.append((kwargs["job_id"], kwargs["state"], kwargs.get("message")))
    )

    def _fake_transcode(*args, cancel_event=None, **kwargs):
        transcode_started.set()
        while cancel_event is not None and not cancel_event.is_set():
            time.sleep(0.01)
        raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled")

    monkeypatch.setattr("desktop_agent.relay_client.transcode_media_to_hls", _fake_transcode)

    client._handle_hls_start(
        fake_ws,  # type: ignore[arg-type]
        {
            "type": "hls.start",
            "jobId": "job_123",
            "relativePath": "lesson-01.mkv",
            "profile": {"heightMax": 720, "videoBitrate": "1800k", "audioBitrate": "128k", "segmentSeconds": 6},
        },
    )
    assert transcode_started.wait(timeout=1)

    client._handle_job_cancel({"type": "job.cancel", "jobId": "job_123", "reason": "viewer disconnected"})
    _wait_until(lambda: client._active_task_counts()["hls"] == 0)

    assert fake_ws.sent == []
    assert state_updates == [
        ("job_123", "RUNNING", None),
        ("job_123", "CANCELLED", "desktop agent HLS job cancelled"),
    ]


def test_relay_client_hls_job_not_found_before_start_does_not_fail_client(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    client = _create_client(media_root)
    fake_ws = _FakeWebSocket()
    transcode_called = False
    reported: list[dict[str, object]] = []

    error = _http_error(
        404,
        "https://plm.xuebao.chat/api/desktop-agents/hls-jobs/job_123/state",
        "404 Client Error: desktop agent HLS job not found: job_123 for url: https://plm.xuebao.chat/api/desktop-agents/hls-jobs/job_123/state",
    )

    def _fake_report_hls_job_state_http(**kwargs) -> None:
        raise error

    def _fake_transcode(*args, **kwargs):
        nonlocal transcode_called
        transcode_called = True
        raise AssertionError("transcode should not run after a missing HLS job")

    client._report_hls_job_state_http = _fake_report_hls_job_state_http  # type: ignore[method-assign]
    client.report_diagnostic_event = lambda **kwargs: reported.append(dict(kwargs)) or True  # type: ignore[method-assign]
    monkeypatch.setattr("desktop_agent.relay_client.transcode_media_to_hls", _fake_transcode)

    client._handle_hls_start(
        fake_ws,  # type: ignore[arg-type]
        {
            "type": "hls.start",
            "jobId": "job_123",
            "relativePath": "lesson-01.mkv",
            "profile": {"heightMax": 720, "videoBitrate": "1800k", "audioBitrate": "128k", "segmentSeconds": 6},
        },
    )

    _wait_until(lambda: client._active_task_counts()["hls"] == 0)
    client._raise_background_error_if_any()

    assert transcode_called is False
    assert reported == [
        {
            "level": "warning",
            "category": "hls",
            "event_type": "hls_cancelled",
            "message": "desktop agent HLS job cancelled",
            "details": {
                "jobId": "job_123",
                "profile": {"heightMax": 720, "videoBitrate": "1800k", "audioBitrate": "128k", "segmentSeconds": 6},
            },
            "project_id": "proj_123",
            "relative_path": "lesson-01.mkv",
        }
    ]


def test_relay_client_hls_artifact_upload_job_not_found_does_not_fail_client(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    client = _create_client(media_root)
    fake_ws = _FakeWebSocket()
    state_updates: list[tuple[str, str, str | None]] = []
    reported: list[dict[str, object]] = []
    output_dir = tmp_path / "hls-output"
    output_dir.mkdir()
    manifest = output_dir / "master.m3u8"
    manifest.write_text("#EXTM3U\n", encoding="utf-8")

    error = _http_error(
        404,
        "https://plm.xuebao.chat/api/desktop-agents/hls-jobs/job_123/artifacts/master.m3u8",
        "404 Client Error: desktop agent HLS job not found: job_123 for url: https://plm.xuebao.chat/api/desktop-agents/hls-jobs/job_123/artifacts/master.m3u8",
    )

    monkeypatch.setattr(
        "desktop_agent.relay_client.transcode_media_to_hls",
        lambda *args, **kwargs: (output_dir, [manifest]),
    )
    client._upload_hls_artifact = lambda **kwargs: (_ for _ in ()).throw(error)  # type: ignore[method-assign]
    client._report_hls_job_state_http = (  # type: ignore[method-assign]
        lambda **kwargs: state_updates.append((kwargs["job_id"], kwargs["state"], kwargs.get("message")))
    )
    client.report_diagnostic_event = lambda **kwargs: reported.append(dict(kwargs)) or True  # type: ignore[method-assign]

    client._handle_hls_start(
        fake_ws,  # type: ignore[arg-type]
        {
            "type": "hls.start",
            "jobId": "job_123",
            "relativePath": "lesson-01.mkv",
            "profile": {"heightMax": 720, "videoBitrate": "1800k", "audioBitrate": "128k", "segmentSeconds": 6},
        },
    )

    _wait_until(lambda: client._active_task_counts()["hls"] == 0)
    client._raise_background_error_if_any()

    assert state_updates == [
        ("job_123", "RUNNING", None),
        ("job_123", "CANCELLED", "desktop agent HLS job cancelled"),
    ]
    assert reported == [
        {
            "level": "warning",
            "category": "hls",
            "event_type": "hls_cancelled",
            "message": "desktop agent HLS job cancelled",
            "details": {
                "jobId": "job_123",
                "profile": {"heightMax": 720, "videoBitrate": "1800k", "audioBitrate": "128k", "segmentSeconds": 6},
            },
            "project_id": "proj_123",
            "relative_path": "lesson-01.mkv",
        }
    ]


def test_relay_client_run_session_preserves_active_hls_task_on_ws_disconnect(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    client = _create_client(media_root)
    transcode_started = Event()
    state_updates: list[tuple[str, str, str | None]] = []
    client._report_local_environment_diagnostics = lambda: None  # type: ignore[method-assign]
    client.sync_manifest = lambda: {"unchanged": True}  # type: ignore[method-assign]
    client.report_diagnostic_event = lambda **kwargs: True  # type: ignore[method-assign]
    client._report_hls_job_state_http = (  # type: ignore[method-assign]
        lambda **kwargs: state_updates.append((kwargs["job_id"], kwargs["state"], kwargs.get("message")))
    )

    def _fake_transcode(*args, cancel_event=None, **kwargs):
        transcode_started.set()
        while cancel_event is not None and not cancel_event.is_set():
            time.sleep(0.01)
        raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled")

    monkeypatch.setattr("desktop_agent.relay_client.transcode_media_to_hls", _fake_transcode)

    class _ClosingWebSocket(_FakeWebSocket):
        def __init__(self) -> None:
            super().__init__()
            self._responses = [
                json.dumps({"type": "connected"}),
                json.dumps(
                    {
                        "type": "hls.start",
                        "jobId": "job_123",
                        "relativePath": "lesson-01.mkv",
                        "profile": {
                            "heightMax": 720,
                            "videoBitrate": "1800k",
                            "audioBitrate": "128k",
                            "segmentSeconds": 6,
                        },
                    }
                ),
                websocket.WebSocketConnectionClosedException("Connection to remote host was lost."),
            ]
            self.closed = False

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self):
            item = self._responses.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        def close(self) -> None:
            self.closed = True

    fake_ws = _ClosingWebSocket()
    monkeypatch.setattr("desktop_agent.relay_client.websocket.create_connection", lambda *args, **kwargs: fake_ws)

    with pytest.raises(websocket.WebSocketConnectionClosedException, match="Connection to remote host was lost"):
        client.run_session()

    assert transcode_started.wait(timeout=1)
    assert client._active_task_counts()["hls"] == 1

    client._handle_job_cancel({"type": "job.cancel", "jobId": "job_123", "reason": "viewer disconnected"})
    _wait_until(lambda: client._active_task_counts()["hls"] == 0)

    assert state_updates == [
        ("job_123", "RUNNING", None),
        ("job_123", "CANCELLED", "desktop agent HLS job cancelled"),
    ]


def test_relay_client_run_session_preserves_active_stream_task_on_ws_disconnect(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "lesson-01.mp4").write_bytes(b"abcdefghij")
    client = _create_client(media_root, stream_chunk_size_bytes=4)
    uploaded_chunks: list[bytes] = []
    first_chunk_uploaded = Event()
    allow_finish = Event()
    client._report_local_environment_diagnostics = lambda: None  # type: ignore[method-assign]
    client.sync_manifest = lambda: {"unchanged": True}  # type: ignore[method-assign]

    def _fake_upload_stream_chunk(**kwargs) -> None:
        uploaded_chunks.append(bytes(kwargs["chunk"]))
        if len(uploaded_chunks) == 1:
            first_chunk_uploaded.set()
            allow_finish.wait(timeout=1)

    client._upload_stream_chunk = _fake_upload_stream_chunk  # type: ignore[method-assign]

    class _ClosingWebSocket(_FakeWebSocket):
        def __init__(self) -> None:
            super().__init__()
            self._responses = [
                json.dumps({"type": "connected"}),
                json.dumps(
                    {
                        "type": "stream.open",
                        "streamId": "stream_123",
                        "relativePath": "lesson-01.mp4",
                        "contentType": "video/mp4",
                        "rangeStart": 0,
                        "rangeEnd": 9,
                    }
                ),
                websocket.WebSocketConnectionClosedException("Connection to remote host was lost."),
            ]
            self.closed = False

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self):
            item = self._responses.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

        def close(self) -> None:
            self.closed = True

    fake_ws = _ClosingWebSocket()
    monkeypatch.setattr("desktop_agent.relay_client.websocket.create_connection", lambda *args, **kwargs: fake_ws)

    with pytest.raises(websocket.WebSocketConnectionClosedException, match="Connection to remote host was lost"):
        client.run_session()

    assert first_chunk_uploaded.wait(timeout=1)
    assert client._active_task_counts()["stream"] == 1

    allow_finish.set()
    _wait_until(lambda: client._active_task_counts()["stream"] == 0)
    client._raise_background_error_if_any()

    assert uploaded_chunks == [b"abcd", b"efgh", b"ij"]


def test_relay_client_run_session_ignores_invalid_websocket_payload(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    client = _create_client(media_root)
    client._report_local_environment_diagnostics = lambda: None  # type: ignore[method-assign]
    client.sync_manifest = lambda: {"unchanged": True}  # type: ignore[method-assign]
    stop_event = Event()
    reported: list[dict[str, object]] = []

    def _report(**kwargs):
        reported.append(dict(kwargs))
        if kwargs.get("event_type") == "ws_invalid_message":
            stop_event.set()
        return True

    client.report_diagnostic_event = _report  # type: ignore[method-assign]

    class _InvalidPayloadWebSocket(_FakeWebSocket):
        def __init__(self) -> None:
            super().__init__()
            self._responses = [
                json.dumps({"type": "connected"}),
                "",
            ]
            self.closed = False

        def settimeout(self, timeout: float) -> None:
            self.timeout = timeout

        def recv(self):
            return self._responses.pop(0)

        def close(self) -> None:
            self.closed = True

    fake_ws = _InvalidPayloadWebSocket()
    monkeypatch.setattr("desktop_agent.relay_client.websocket.create_connection", lambda *args, **kwargs: fake_ws)

    client.run_session(stop_event=stop_event)

    assert fake_ws.closed is True
    assert reported == [
        {
            "level": "warning",
            "category": "service",
            "event_type": "ws_invalid_message",
            "message": "ignored invalid websocket payload",
            "details": {"payloadType": "str", "payloadLength": 0, "payloadPreview": ""},
            "project_id": "proj_123",
        }
    ]


def test_relay_client_probe_failure_reports_diagnostic_event(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    (media_root / "lesson-01.mkv").write_bytes(b"video-bytes")
    client = _create_client(media_root)
    fake_ws = _FakeWebSocket()
    reported: list[dict[str, object]] = []

    monkeypatch.setattr("desktop_agent.relay_client.probe_media_file", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("ffprobe missing")))
    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: None)
    client.report_diagnostic_event = lambda **kwargs: reported.append(dict(kwargs)) or True  # type: ignore[method-assign]

    client._handle_probe_request(
        fake_ws,  # type: ignore[arg-type]
        {
            "type": "probe.request",
            "requestId": "probe_123",
            "projectId": "proj_123",
            "instanceId": "inst_123",
            "relativePath": "lesson-01.mkv",
        },
    )

    assert len(reported) == 1
    assert reported[0]["level"] == "warning"
    assert reported[0]["category"] == "probe"
    assert reported[0]["event_type"] == "probe_failed"
    assert reported[0]["message"] == "ffprobe missing"
    assert reported[0]["project_id"] == "proj_123"
    assert reported[0]["instance_id"] == "inst_123"
    assert reported[0]["relative_path"] == "lesson-01.mkv"
    assert reported[0]["details"]["requestId"] == "probe_123"
    assert reported[0]["details"]["ffprobePath"] is None
    assert reported[0]["details"]["sizeBytes"] == 11
    assert isinstance(reported[0]["details"]["modifiedAt"], str)
    assert fake_ws.sent[-1]["type"] == "probe.result"
    assert fake_ws.sent[-1]["error"] == "ffprobe missing"


def test_relay_client_local_environment_diagnostics_are_deduplicated(monkeypatch, tmp_path: Path) -> None:
    media_root = tmp_path / "media"
    media_root.mkdir()
    client = _create_client(media_root)
    reported: list[dict[str, object]] = []

    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: None)
    client.report_diagnostic_event = lambda **kwargs: reported.append(dict(kwargs)) or True  # type: ignore[method-assign]

    client._report_local_environment_diagnostics()
    client._report_local_environment_diagnostics()

    assert reported == [
        {
            "level": "warning",
            "category": "probe",
            "event_type": "ffprobe_missing",
            "message": "ffprobe executable is not available",
            "details": {"rootDir": str(media_root), "toolPath": None},
            "project_id": "proj_123",
            "instance_id": None,
            "relative_path": None,
        },
        {
            "level": "warning",
            "category": "hls",
            "event_type": "ffmpeg_missing",
            "message": "ffmpeg executable is not available",
            "details": {"rootDir": str(media_root), "toolPath": None},
            "project_id": "proj_123",
            "instance_id": None,
            "relative_path": None,
        },
    ]


def test_raise_for_agent_response_surfaces_backend_error_message() -> None:
    response = requests.Response()
    response.status_code = 400
    response.reason = "Bad Request"
    response.url = "https://plm.xuebao.chat/api/desktop-agents/manifest-sync"
    response._content = (
        b'{"ok":false,"error":{"code":"NOT_FOUND","message":"Project not found or not ACTIVE: ML"}}'
    )
    response.headers["Content-Type"] = "application/json"

    with pytest.raises(requests.HTTPError, match="Project not found or not ACTIVE: ML"):
        _raise_for_agent_response(response)


def test_raise_for_agent_response_preserves_auth_expired_behavior() -> None:
    response = requests.Response()
    response.status_code = 401
    response.reason = "Unauthorized"
    response.url = "https://plm.xuebao.chat/api/desktop-agents/manifest-sync"

    with pytest.raises(DesktopAgentAuthExpired):
        _raise_for_agent_response(response)
