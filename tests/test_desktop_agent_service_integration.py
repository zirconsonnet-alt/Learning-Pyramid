from __future__ import annotations

import asyncio
import json
import socket
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Awaitable, Callable

import pytest
import uvicorn
from fastapi import FastAPI, Request, WebSocket
from starlette.websockets import WebSocketDisconnect

from desktop_agent.config_store import AgentConfig, ConfigStore
from desktop_agent.relay_client import RelayClient
from desktop_agent.service import DesktopAgentService


def _seed_config(tmp_path: Path, *, server_url: str) -> ConfigStore:
    store = ConfigStore(tmp_path)
    store.save(
        AgentConfig(
            server_url=server_url,
            agent_id="agent_123",
            agent_token="agent-token-1",
            refresh_token="refresh-token-1",
            project_id="proj_123",
            root_dir=str(tmp_path),
            device_name="BYLOU-PC",
        )
    )
    return store


def _wait_until(predicate: Callable[[], bool], *, timeout_seconds: float = 5.0, interval_seconds: float = 0.02) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(interval_seconds)
    raise AssertionError("condition not satisfied before timeout")


def _reserve_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass
class _FakeRelayServerState:
    connection_count: int = 0
    manifest_sync_payloads: list[dict[str, Any]] = field(default_factory=list)
    diagnostic_payloads: list[dict[str, Any]] = field(default_factory=list)
    upload_events: list[tuple[float, str, bytes]] = field(default_factory=list)
    status_sync_payloads: list[dict[str, Any]] = field(default_factory=list)
    heartbeat_count: int = 0
    first_connected: Event = field(default_factory=Event)
    reconnected: Event = field(default_factory=Event)
    first_chunk_uploaded: Event = field(default_factory=Event)
    all_chunks_uploaded: Event = field(default_factory=Event)
    lock: Lock = field(default_factory=Lock)
    uploaded_bytes: bytes = b""
    expected_bytes: bytes = b""
    first_ws_closed_at: float | None = None

    def next_connection_index(self) -> int:
        with self.lock:
            self.connection_count += 1
            return self.connection_count

    def record_upload(self, *, stream_id: str, content: bytes) -> None:
        now = time.monotonic()
        with self.lock:
            self.upload_events.append((now, stream_id, bytes(content)))
            self.uploaded_bytes += bytes(content)
            uploaded_len = len(self.uploaded_bytes)
        self.first_chunk_uploaded.set()
        if self.expected_bytes and uploaded_len >= len(self.expected_bytes):
            self.all_chunks_uploaded.set()


class _LocalRelayServer:
    def __init__(
        self,
        *,
        port: int,
        state: _FakeRelayServerState,
        after_hello: Callable[[WebSocket, int], Awaitable[None] | None] | None = None,
        upload_delay_seconds: float = 0.0,
    ) -> None:
        self.port = int(port)
        self.state = state
        self._after_hello = after_hello
        self._upload_delay_seconds = max(0.0, float(upload_delay_seconds))
        self._app = FastAPI()
        self._configure_routes()
        self._server = uvicorn.Server(
            uvicorn.Config(
                self._app,
                host="127.0.0.1",
                port=self.port,
                log_level="error",
                access_log=False,
                lifespan="off",
            )
        )
        self._thread = Thread(target=self._server.run, name=f"fake-relay-{self.port}", daemon=True)

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def _configure_routes(self) -> None:
        app = self._app
        state = self.state
        after_hello = self._after_hello
        upload_delay_seconds = self._upload_delay_seconds

        @app.post("/api/desktop-agents/manifest-sync")
        async def manifest_sync(request: Request) -> dict[str, Any]:
            payload = await request.json()
            state.manifest_sync_payloads.append(dict(payload))
            return {"ok": True, "data": {"accepted": True}}

        @app.post("/api/desktop-agents/diagnostic-events")
        async def diagnostic_events(request: Request) -> dict[str, Any]:
            payload = await request.json()
            state.diagnostic_payloads.append(dict(payload))
            return {"ok": True, "data": {"accepted": True}}

        @app.put("/api/desktop-agents/stream-sessions/{stream_id}/chunks")
        async def upload_stream_chunk(stream_id: str, request: Request) -> dict[str, Any]:
            if upload_delay_seconds > 0:
                await asyncio.sleep(upload_delay_seconds)
            payload = await request.body()
            state.record_upload(stream_id=stream_id, content=payload)
            return {"ok": True, "data": {"accepted": True}}

        @app.websocket("/api/desktop-agents/ws")
        async def relay_ws(websocket: WebSocket) -> None:
            await websocket.accept()
            connection_index = state.next_connection_index()
            await websocket.send_json({"type": "connected"})
            try:
                while True:
                    raw = await websocket.receive_text()
                    payload = json.loads(raw)
                    message_type = str(payload.get("type", ""))
                    if message_type == "hello":
                        if connection_index == 1:
                            state.first_connected.set()
                        else:
                            state.reconnected.set()
                        await websocket.send_json({"type": "hello.ack"})
                        if after_hello is not None:
                            maybe_awaitable = after_hello(websocket, connection_index)
                            if maybe_awaitable is not None:
                                await maybe_awaitable
                        continue
                    if message_type == "heartbeat":
                        state.heartbeat_count += 1
                        await websocket.send_json({"type": "heartbeat.ack"})
                        continue
                    if message_type == "status.sync":
                        state.status_sync_payloads.append(dict(payload))
                        continue
            except WebSocketDisconnect:
                return

    def start(self) -> None:
        self._thread.start()
        _wait_until(lambda: bool(self._server.started), timeout_seconds=5.0)

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5.0)
        if self._thread.is_alive():
            raise AssertionError(f"fake relay server on port {self.port} did not stop in time")
        _wait_until(lambda: not self._can_connect(), timeout_seconds=5.0)

    def _can_connect(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.1):
                return True
        except OSError:
            return False


def _run_service_in_thread(
    service: DesktopAgentService,
    *,
    stop_event: Event,
    statuses: list[tuple[str, str | None]],
) -> tuple[Thread, dict[str, BaseException]]:
    holder: dict[str, BaseException] = {}

    def _target() -> None:
        try:
            service.run_forever(stop_event=stop_event, status_callback=lambda state, message: statuses.append((state, message)))
        except BaseException as exc:  # pragma: no cover - surfaced via assertion
            holder["exception"] = exc

    thread = Thread(target=_target, name="desktop-agent-service-test", daemon=True)
    thread.start()
    return thread, holder


def _join_service_thread(thread: Thread, holder: dict[str, BaseException], *, timeout_seconds: float = 10.0) -> None:
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise AssertionError("desktop agent service thread did not stop in time")
    if "exception" in holder:
        raise holder["exception"]


def test_desktop_agent_service_recovers_after_short_server_unreachable_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    port = _reserve_free_port()
    store = _seed_config(tmp_path, server_url=f"http://127.0.0.1:{port}")
    state = _FakeRelayServerState()
    stop_event = Event()
    statuses: list[tuple[str, str | None]] = []

    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: str(tmp_path / f"{name}.exe"))

    service = DesktopAgentService(
        config_store=store,
        client_factory=lambda config: RelayClient(config, stream_chunk_size_bytes=2),
        reconnect_delay_seconds=0.1,
        refresh_interval_seconds=60,
        sleep_fn=time.sleep,
    )
    thread, holder = _run_service_in_thread(service, stop_event=stop_event, statuses=statuses)

    _wait_until(lambda: any(state_name == "ERROR" for state_name, _ in statuses), timeout_seconds=3.0)

    server = _LocalRelayServer(port=port, state=state)
    server.start()
    try:
        _wait_until(state.first_connected.is_set, timeout_seconds=5.0)
        _wait_until(lambda: len(state.manifest_sync_payloads) >= 1, timeout_seconds=5.0)
        stop_event.set()
        _join_service_thread(thread, holder)
    finally:
        server.stop()

    state_names = [state_name for state_name, _ in statuses]
    assert state_names[0] == "STARTING"
    assert "ERROR" in state_names
    assert "RUNNING" in state_names
    assert state_names[-1] == "STOPPED"
    assert state.connection_count >= 1


def test_desktop_agent_service_recovers_when_only_websocket_disconnects_but_http_uploads_continue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    media_file = tmp_path / "lesson-01.mp4"
    media_file.write_bytes(b"abcdefghij")

    state = _FakeRelayServerState(expected_bytes=media_file.read_bytes())
    port = _reserve_free_port()
    store = _seed_config(tmp_path, server_url=f"http://127.0.0.1:{port}")
    stop_event = Event()
    statuses: list[tuple[str, str | None]] = []

    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: str(tmp_path / f"{name}.exe"))

    async def _after_hello(websocket: WebSocket, connection_index: int) -> None:
        if connection_index == 1:
            await websocket.send_json(
                {
                    "type": "stream.open",
                    "streamId": "stream_123",
                    "relativePath": media_file.name,
                    "contentType": "video/mp4",
                    "rangeStart": 0,
                    "rangeEnd": len(state.expected_bytes) - 1,
                }
            )
            await asyncio.to_thread(state.first_chunk_uploaded.wait, 5.0)
            state.first_ws_closed_at = time.monotonic()
            await websocket.close(code=1012)

    server = _LocalRelayServer(
        port=port,
        state=state,
        after_hello=_after_hello,
        upload_delay_seconds=0.05,
    )
    server.start()

    service = DesktopAgentService(
        config_store=store,
        client_factory=lambda config: RelayClient(config, stream_chunk_size_bytes=2),
        reconnect_delay_seconds=0.1,
        refresh_interval_seconds=60,
        sleep_fn=time.sleep,
    )
    thread, holder = _run_service_in_thread(service, stop_event=stop_event, statuses=statuses)

    try:
        _wait_until(state.all_chunks_uploaded.is_set, timeout_seconds=6.0)
        _wait_until(state.reconnected.is_set, timeout_seconds=6.0)
        _wait_until(
            lambda: any(int(payload.get("activeStreams", 0)) >= 1 for payload in state.status_sync_payloads),
            timeout_seconds=6.0,
        )
        stop_event.set()
        _join_service_thread(thread, holder)
    finally:
        server.stop()

    assert state.uploaded_bytes == state.expected_bytes
    assert state.first_ws_closed_at is not None
    uploads_after_disconnect = [
        chunk
        for uploaded_at, _stream_id, chunk in state.upload_events
        if state.first_ws_closed_at is not None and uploaded_at > state.first_ws_closed_at
    ]
    assert uploads_after_disconnect

    state_names = [state_name for state_name, _ in statuses]
    assert state_names.count("RUNNING") >= 2
    assert "ERROR" in state_names


def test_desktop_agent_service_recovers_after_brief_network_outage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    port = _reserve_free_port()
    state = _FakeRelayServerState()
    stop_event = Event()
    statuses: list[tuple[str, str | None]] = []

    monkeypatch.setattr("desktop_agent.relay_client.resolve_media_tool_path", lambda name: str(tmp_path / f"{name}.exe"))

    server = _LocalRelayServer(port=port, state=state)
    server.start()

    store = _seed_config(tmp_path, server_url=server.base_url)
    service = DesktopAgentService(
        config_store=store,
        client_factory=lambda config: RelayClient(config, stream_chunk_size_bytes=2),
        reconnect_delay_seconds=0.1,
        refresh_interval_seconds=60,
        sleep_fn=time.sleep,
    )
    thread, holder = _run_service_in_thread(service, stop_event=stop_event, statuses=statuses)

    try:
        _wait_until(state.first_connected.is_set, timeout_seconds=5.0)
        server.stop()
        _wait_until(
            lambda: sum(1 for state_name, _ in statuses if state_name == "ERROR") >= 1,
            timeout_seconds=5.0,
        )
        time.sleep(0.35)

        replacement = _LocalRelayServer(port=port, state=state)
        replacement.start()
        try:
            _wait_until(lambda: state.connection_count >= 2 and state.reconnected.is_set(), timeout_seconds=5.0)
            stop_event.set()
            _join_service_thread(thread, holder)
        finally:
            replacement.stop()
    except Exception:
        stop_event.set()
        _join_service_thread(thread, holder)
        raise

    state_names = [state_name for state_name, _ in statuses]
    assert state_names.count("RUNNING") >= 2
    assert "ERROR" in state_names
    assert state_names[-1] == "STOPPED"
    assert state.connection_count >= 2
