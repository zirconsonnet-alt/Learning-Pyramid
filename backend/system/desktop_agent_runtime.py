from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import WebSocket
from backend.models.errors import PreconditionFailure


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _coerce_utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _env_positive_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return float(default)
    try:
        value = float(raw)
    except Exception:
        return float(default)
    return float(default) if value <= 0 else value


def _env_positive_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return int(default) if value <= 0 else value


@dataclass(frozen=True, slots=True)
class DesktopAgentRelayRuntimeConfig:
    probe_timeout_seconds: float
    stream_header_timeout_seconds: float
    stream_idle_timeout_seconds: float
    max_concurrent_streams_per_agent: int
    max_concurrent_viewers_per_user: int


def current_desktop_agent_relay_runtime_config() -> DesktopAgentRelayRuntimeConfig:
    return DesktopAgentRelayRuntimeConfig(
        probe_timeout_seconds=_env_positive_float("PLM_AGENT_PROBE_TIMEOUT_SECONDS", 15.0),
        stream_header_timeout_seconds=_env_positive_float("PLM_AGENT_STREAM_HEADER_TIMEOUT_SECONDS", 30.0),
        stream_idle_timeout_seconds=_env_positive_float("PLM_AGENT_STREAM_IDLE_TIMEOUT_SECONDS", 15.0),
        max_concurrent_streams_per_agent=_env_positive_int("PLM_AGENT_MAX_CONCURRENT_STREAMS_PER_AGENT", 1),
        max_concurrent_viewers_per_user=_env_positive_int("PLM_AGENT_MAX_CONCURRENT_VIEWERS_PER_USER", 2),
    )


class DesktopAgentRuntimeError(RuntimeError):
    pass


class DesktopAgentNotConnectedError(DesktopAgentRuntimeError):
    pass


class DesktopAgentStreamNotFoundError(DesktopAgentRuntimeError):
    pass


class DesktopAgentStreamClosedError(DesktopAgentRuntimeError):
    pass


class DesktopAgentStreamTimeoutError(DesktopAgentRuntimeError):
    pass


class DesktopAgentStreamLimitError(DesktopAgentRuntimeError):
    pass


class DesktopAgentProbeNotFoundError(DesktopAgentRuntimeError):
    pass


class DesktopAgentProbeTimeoutError(DesktopAgentRuntimeError):
    pass


class DesktopAgentProbeClosedError(DesktopAgentRuntimeError):
    pass


class DesktopAgentHlsJobNotFoundError(DesktopAgentRuntimeError):
    pass


@dataclass
class _AgentConnection:
    websocket: WebSocket
    pending_commands: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)


@dataclass
class _StreamHeaders:
    content_type: str
    file_size: int | None
    range_start: int | None
    range_end: int | None


@dataclass(frozen=True)
class _StreamTerminal:
    kind: str
    message: str | None = None


@dataclass
class _StreamSession:
    stream_id: str
    agent_id: str
    user_id: str
    project_id: str
    instance_id: str
    relative_path: str
    content_type: str
    created_at: str
    expires_at: str
    idle_timeout_seconds: float
    headers_wait_timeout_seconds: float
    created_monotonic: float
    last_activity_monotonic: float
    connection_lost_at: str | None = None
    headers_ready: threading.Event = field(default_factory=threading.Event)
    chunk_queue: queue.Queue[bytes | _StreamTerminal] = field(default_factory=queue.Queue)
    headers: _StreamHeaders | None = None
    terminal: _StreamTerminal | None = None


@dataclass
class _ProbeRequest:
    request_id: str
    agent_id: str
    project_id: str
    instance_id: str
    relative_path: str
    created_at: str
    expires_at: str
    timeout_seconds: float
    result_ready: threading.Event = field(default_factory=threading.Event)
    result_payload: dict[str, Any] | None = None
    terminal_message: str | None = None


@dataclass
class _HlsJob:
    job_id: str
    cache_key: str
    agent_id: str
    project_id: str
    instance_id: str
    relative_path: str
    profile: dict[str, Any]
    created_at: str
    updated_at: str
    expires_at: str
    state: str = "OPENING"
    message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    last_artifact_at: str | None = None
    connection_lost_at: str | None = None
    artifact_count: int = 0
    artifact_bytes: int = 0


@dataclass
class _RuntimeTelemetry:
    hls_cache_hit_count: int = 0
    hls_cache_miss_count: int = 0
    hls_artifact_request_count: int = 0
    hls_artifact_bytes_served: int = 0
    reaped_stream_count: int = 0
    reaped_probe_count: int = 0
    reaped_hls_job_count: int = 0
    reap_reason_counts: dict[str, int] = field(default_factory=dict)
    last_reaped_at: str | None = None


class DesktopAgentRuntime:
    def __init__(self, config: DesktopAgentRelayRuntimeConfig | None = None) -> None:
        self._config = config or current_desktop_agent_relay_runtime_config()
        self._stream_disconnect_grace_seconds = _env_positive_float("PLM_AGENT_STREAM_DISCONNECT_GRACE_SECONDS", 10.0)
        self._hls_disconnect_grace_seconds = _env_positive_float("PLM_AGENT_HLS_DISCONNECT_GRACE_SECONDS", 30.0)
        self._guard = threading.RLock()
        self._connections: dict[str, _AgentConnection] = {}
        self._stream_sessions: dict[str, _StreamSession] = {}
        self._probe_requests: dict[str, _ProbeRequest] = {}
        self._hls_jobs: dict[str, _HlsJob] = {}
        self._hls_job_ids_by_cache_key: dict[str, str] = {}
        self._telemetry = _RuntimeTelemetry()

    @property
    def config(self) -> DesktopAgentRelayRuntimeConfig:
        return self._config

    def _active_stream_count_for_agent_locked(self, agent_id: str) -> int:
        return sum(
            1
            for session in self._stream_sessions.values()
            if session.agent_id == str(agent_id) and session.terminal is None
        )

    def _active_stream_count_for_user_locked(self, user_id: str) -> int:
        return sum(
            1
            for session in self._stream_sessions.values()
            if session.user_id == str(user_id) and session.terminal is None
        )

    def _close_session_locked(self, session: _StreamSession, *, kind: str, message: str | None = None) -> None:
        if session.terminal is not None:
            return
        session.terminal = _StreamTerminal(kind=kind, message=message)
        session.headers_ready.set()
        session.chunk_queue.put(session.terminal)

    def _terminal_error(self, terminal: _StreamTerminal | None) -> DesktopAgentRuntimeError:
        current = terminal or _StreamTerminal(kind="closed", message="desktop agent stream session closed")
        message = str(current.message or "desktop agent stream session closed")
        if current.kind == "timeout":
            return DesktopAgentStreamTimeoutError(message)
        return DesktopAgentStreamClosedError(message)

    def _enqueue_command_locked(self, agent_id: str, payload: dict[str, Any]) -> bool:
        connection = self._connections.get(str(agent_id))
        if connection is None:
            return False
        connection.pending_commands.put(dict(payload))
        return True

    def _record_reap_reason_locked(self, reason: str) -> None:
        key = str(reason or "").strip() or "unknown"
        self._telemetry.reap_reason_counts[key] = self._telemetry.reap_reason_counts.get(key, 0) + 1
        self._telemetry.last_reaped_at = _utc_now_text()

    def _stream_disconnect_grace_expired_locked(self, session: _StreamSession) -> bool:
        lost_at = str(session.connection_lost_at or "").strip()
        if not lost_at:
            return False
        deadline = _coerce_utc_datetime(lost_at) + timedelta(seconds=self._stream_disconnect_grace_seconds)
        return deadline <= datetime.now(timezone.utc).astimezone(timezone.utc)

    def _fail_stream_after_disconnect_grace(self, stream_id: str) -> bool:
        with self._guard:
            session = self._stream_sessions.get(str(stream_id))
            if session is None or session.terminal is not None:
                return False
            if not self._stream_disconnect_grace_expired_locked(session):
                return False
            self._close_session_locked(session, kind="closed", message="desktop agent disconnected during relay")
            return True

    def is_agent_connected(self, agent_id: str) -> bool:
        with self._guard:
            return str(agent_id) in self._connections

    def register_connection(self, agent_id: str, websocket: WebSocket) -> None:
        with self._guard:
            previous = self._connections.get(str(agent_id))
            connection = _AgentConnection(websocket=websocket)
            if previous is not None:
                while True:
                    try:
                        connection.pending_commands.put(previous.pending_commands.get_nowait())
                    except queue.Empty:
                        break
            self._connections[str(agent_id)] = connection
            for session in self._stream_sessions.values():
                if session.agent_id != str(agent_id):
                    continue
                if session.terminal is not None:
                    continue
                session.connection_lost_at = None
            for job in self._hls_jobs.values():
                if job.agent_id != str(agent_id):
                    continue
                if job.state in {"COMPLETED", "FAILED", "CANCELLED"}:
                    continue
                job.connection_lost_at = None

    def unregister_connection(self, agent_id: str, websocket: WebSocket | None = None) -> tuple[str, ...]:
        affected_stream_ids: list[str] = []
        with self._guard:
            current = self._connections.get(str(agent_id))
            if current is None:
                return ()
            if websocket is not None and current.websocket is not websocket:
                return ()
            self._connections.pop(str(agent_id), None)
            disconnected_at = _utc_now_text()
            for session in self._stream_sessions.values():
                if session.agent_id != str(agent_id):
                    continue
                if session.terminal is not None:
                    continue
                session.connection_lost_at = disconnected_at
                affected_stream_ids.append(session.stream_id)
            for probe in self._probe_requests.values():
                if probe.agent_id != str(agent_id):
                    continue
                if probe.result_ready.is_set():
                    continue
                probe.terminal_message = "desktop agent disconnected during media probe"
                probe.result_ready.set()
            for job in self._hls_jobs.values():
                if job.agent_id != str(agent_id):
                    continue
                if job.state in {"COMPLETED", "FAILED", "CANCELLED"}:
                    continue
                job.connection_lost_at = _utc_now_text()
        return tuple(affected_stream_ids)

    def enqueue_command(self, agent_id: str, payload: dict[str, Any]) -> None:
        with self._guard:
            enqueued = self._enqueue_command_locked(agent_id, payload)
        if not enqueued:
            raise DesktopAgentNotConnectedError("desktop agent is not connected")

    def record_hls_cache_lookup(self, *, hit: bool) -> None:
        with self._guard:
            if hit:
                self._telemetry.hls_cache_hit_count += 1
            else:
                self._telemetry.hls_cache_miss_count += 1

    def record_hls_artifact_served(self, *, size_bytes: int) -> None:
        with self._guard:
            self._telemetry.hls_artifact_request_count += 1
            self._telemetry.hls_artifact_bytes_served += max(0, int(size_bytes))

    def drain_commands(self, agent_id: str, websocket: WebSocket | None = None) -> list[dict[str, Any]]:
        with self._guard:
            connection = self._connections.get(str(agent_id))
        if connection is None:
            return []
        if websocket is not None and connection.websocket is not websocket:
            return []
        items: list[dict[str, Any]] = []
        while True:
            try:
                items.append(connection.pending_commands.get_nowait())
            except queue.Empty:
                break
        return items

    def create_stream_session(
        self,
        *,
        agent_id: str,
        user_id: str,
        project_id: str,
        instance_id: str,
        relative_path: str,
        content_type: str,
        ttl_seconds: int | None = None,
    ) -> _StreamSession:
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        created_monotonic = time.monotonic()
        expires_in_seconds = max(
            60,
            int(ttl_seconds if ttl_seconds is not None else max(
                self._config.stream_header_timeout_seconds,
                self._config.stream_idle_timeout_seconds,
            ) * 4),
        )
        session = _StreamSession(
            stream_id=f"stream_{uuid.uuid4().hex}",
            agent_id=str(agent_id),
            user_id=str(user_id),
            project_id=str(project_id),
            instance_id=str(instance_id),
            relative_path=str(relative_path),
            content_type=str(content_type),
            created_at=created_at.isoformat(),
            expires_at=(created_at + timedelta(seconds=expires_in_seconds)).isoformat(),
            idle_timeout_seconds=self._config.stream_idle_timeout_seconds,
            headers_wait_timeout_seconds=self._config.stream_header_timeout_seconds,
            created_monotonic=created_monotonic,
            last_activity_monotonic=created_monotonic,
        )
        with self._guard:
            active_for_agent = self._active_stream_count_for_agent_locked(session.agent_id)
            if active_for_agent >= self._config.max_concurrent_streams_per_agent:
                raise DesktopAgentStreamLimitError("desktop agent concurrent stream limit reached")
            active_for_user = self._active_stream_count_for_user_locked(session.user_id)
            if active_for_user >= self._config.max_concurrent_viewers_per_user:
                raise DesktopAgentStreamLimitError("viewer concurrent stream limit reached")
            self._stream_sessions[session.stream_id] = session
        return session

    def create_probe_request(
        self,
        *,
        agent_id: str,
        project_id: str,
        instance_id: str,
        relative_path: str,
    ) -> _ProbeRequest:
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        probe = _ProbeRequest(
            request_id=f"probe_{uuid.uuid4().hex}",
            agent_id=str(agent_id),
            project_id=str(project_id),
            instance_id=str(instance_id),
            relative_path=str(relative_path),
            created_at=created_at.isoformat(),
            expires_at=(created_at + timedelta(seconds=max(1, int(self._config.probe_timeout_seconds)))).isoformat(),
            timeout_seconds=self._config.probe_timeout_seconds,
        )
        with self._guard:
            self._probe_requests[probe.request_id] = probe
        return probe

    def resolve_probe_request(self, request_id: str, *, agent_id: str, payload: dict[str, Any]) -> None:
        with self._guard:
            probe = self._probe_requests.get(str(request_id))
            if probe is None:
                raise DesktopAgentProbeNotFoundError(f"desktop agent probe request not found: {request_id}")
            if probe.agent_id != str(agent_id):
                raise PermissionError("probe request agent mismatch")
            probe.result_payload = dict(payload)
            probe.result_ready.set()

    async def wait_for_probe_result(self, request_id: str, timeout_seconds: float | None = None) -> dict[str, Any]:
        with self._guard:
            probe = self._probe_requests.get(str(request_id))
        if probe is None:
            raise DesktopAgentProbeNotFoundError(f"desktop agent probe request not found: {request_id}")
        timeout = probe.timeout_seconds if timeout_seconds is None else max(0.0, float(timeout_seconds))
        is_ready = await asyncio.to_thread(probe.result_ready.wait, timeout)
        if not is_ready:
            self.release_probe_request(request_id)
            raise DesktopAgentProbeTimeoutError("desktop agent media probe timed out")
        if probe.result_payload is None:
            self.release_probe_request(request_id)
            raise DesktopAgentProbeClosedError(str(probe.terminal_message or "desktop agent media probe closed"))
        payload = dict(probe.result_payload)
        self.release_probe_request(request_id)
        return payload

    def release_probe_request(self, request_id: str) -> None:
        with self._guard:
            self._probe_requests.pop(str(request_id), None)

    def create_or_get_hls_job(
        self,
        *,
        cache_key: str,
        agent_id: str,
        project_id: str,
        instance_id: str,
        relative_path: str,
        profile: dict[str, Any],
    ) -> tuple[_HlsJob, bool]:
        created_at = datetime.now(timezone.utc).replace(microsecond=0)
        with self._guard:
            existing_job_id = self._hls_job_ids_by_cache_key.get(str(cache_key))
            if existing_job_id is not None:
                existing = self._hls_jobs.get(existing_job_id)
                if existing is not None and existing.state not in {"COMPLETED", "FAILED", "CANCELLED"}:
                    return existing, False
            job = _HlsJob(
                job_id=f"job_{uuid.uuid4().hex}",
                cache_key=str(cache_key),
                agent_id=str(agent_id),
                project_id=str(project_id),
                instance_id=str(instance_id),
                relative_path=str(relative_path),
                profile=dict(profile),
                created_at=created_at.isoformat(),
                updated_at=created_at.isoformat(),
                expires_at=(created_at + timedelta(hours=1)).isoformat(),
            )
            self._hls_jobs[job.job_id] = job
            self._hls_job_ids_by_cache_key[job.cache_key] = job.job_id
            return job, True

    def get_hls_job(self, job_id: str) -> _HlsJob:
        with self._guard:
            job = self._hls_jobs.get(str(job_id))
        if job is None:
            raise DesktopAgentHlsJobNotFoundError(f"desktop agent HLS job not found: {job_id}")
        return job

    def get_hls_job_by_cache_key(self, cache_key: str) -> _HlsJob | None:
        with self._guard:
            job_id = self._hls_job_ids_by_cache_key.get(str(cache_key))
            if job_id is None:
                return None
            return self._hls_jobs.get(job_id)

    def update_hls_job_state(self, job_id: str, *, agent_id: str, state: str, message: str | None = None) -> _HlsJob:
        next_state = str(state or "").strip().upper()
        if next_state not in {"OPENING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"}:
            raise PreconditionFailure("desktop agent HLS job state is invalid")
        with self._guard:
            job = self._hls_jobs.get(str(job_id))
            if job is None:
                raise DesktopAgentHlsJobNotFoundError(f"desktop agent HLS job not found: {job_id}")
            if job.agent_id != str(agent_id):
                raise PermissionError("HLS job agent mismatch")
            now_text = _utc_now_text()
            job.state = next_state
            job.message = None if message is None else str(message)
            job.updated_at = now_text
            job.connection_lost_at = None
            if next_state == "RUNNING" and not str(job.started_at or "").strip():
                job.started_at = now_text
            if next_state in {"COMPLETED", "FAILED", "CANCELLED"}:
                if not str(job.started_at or "").strip():
                    job.started_at = now_text
                job.finished_at = now_text
            else:
                job.finished_at = None
            return job

    def cancel_hls_job(self, job_id: str, *, reason: str, notify_agent: bool = False) -> _HlsJob:
        with self._guard:
            job = self._hls_jobs.get(str(job_id))
            if job is None:
                raise DesktopAgentHlsJobNotFoundError(f"desktop agent HLS job not found: {job_id}")
            if job.state in {"COMPLETED", "FAILED", "CANCELLED"}:
                return job
            job.state = "CANCELLED"
            job.message = str(reason)
            now_text = _utc_now_text()
            job.updated_at = now_text
            if not str(job.started_at or "").strip():
                job.started_at = now_text
            job.finished_at = now_text
            if notify_agent:
                self._enqueue_command_locked(
                    job.agent_id,
                    {
                        "type": "job.cancel",
                        "jobId": job.job_id,
                        "reason": str(reason),
                    },
                )
            return job

    def get_stream_session(self, stream_id: str) -> _StreamSession:
        with self._guard:
            session = self._stream_sessions.get(str(stream_id))
        if session is None:
            raise DesktopAgentStreamNotFoundError(f"desktop agent stream session not found: {stream_id}")
        return session

    def cancel_stream_session(self, stream_id: str, *, reason: str, notify_agent: bool = False) -> None:
        with self._guard:
            session = self._stream_sessions.get(str(stream_id))
            if session is None:
                return
            if session.terminal is not None:
                return
            self._close_session_locked(session, kind="closed", message=str(reason))
            if notify_agent:
                self._enqueue_command_locked(
                    session.agent_id,
                    {
                        "type": "stream.cancel",
                        "streamId": session.stream_id,
                        "reason": str(reason),
                    },
                )

    def record_hls_job_artifact(self, job_id: str, *, size_bytes: int) -> _HlsJob:
        with self._guard:
            job = self._hls_jobs.get(str(job_id))
            if job is None:
                raise DesktopAgentHlsJobNotFoundError(f"desktop agent HLS job not found: {job_id}")
            now_text = _utc_now_text()
            job.updated_at = now_text
            job.last_artifact_at = now_text
            job.connection_lost_at = None
            if not str(job.started_at or "").strip():
                job.started_at = now_text
            job.artifact_count += 1
            job.artifact_bytes += max(0, int(size_bytes))
            return job

    def list_hls_jobs(self, *, agent_id: str | None = None) -> tuple[_HlsJob, ...]:
        with self._guard:
            items = tuple(
                job
                for job in self._hls_jobs.values()
                if agent_id is None or job.agent_id == str(agent_id)
            )
        return items

    def reap_expired(self, *, now: datetime | None = None) -> dict[str, tuple[str, ...]]:
        cutoff = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        expired_stream_ids: list[str] = []
        expired_probe_ids: list[str] = []
        expired_hls_job_ids: list[str] = []
        with self._guard:
            for session in self._stream_sessions.values():
                if session.terminal is not None:
                    continue
                if _coerce_utc_datetime(session.expires_at) > cutoff:
                    continue
                self._close_session_locked(session, kind="timeout", message="desktop agent stream session expired")
                self._enqueue_command_locked(
                    session.agent_id,
                    {
                        "type": "stream.cancel",
                        "streamId": session.stream_id,
                        "reason": "desktop agent stream session expired",
                    },
                )
                self._telemetry.reaped_stream_count += 1
                self._record_reap_reason_locked("desktop agent stream session expired")
                expired_stream_ids.append(session.stream_id)
            for probe in self._probe_requests.values():
                if probe.result_ready.is_set():
                    continue
                if _coerce_utc_datetime(probe.expires_at) > cutoff:
                    continue
                probe.terminal_message = "desktop agent media probe expired"
                probe.result_ready.set()
                self._telemetry.reaped_probe_count += 1
                self._record_reap_reason_locked("desktop agent media probe expired")
                expired_probe_ids.append(probe.request_id)
            for job in self._hls_jobs.values():
                if job.state in {"COMPLETED", "FAILED", "CANCELLED"}:
                    continue
                if str(job.connection_lost_at or "").strip():
                    disconnected_at = _coerce_utc_datetime(job.connection_lost_at)
                    disconnect_deadline = disconnected_at + timedelta(seconds=self._hls_disconnect_grace_seconds)
                    if disconnect_deadline <= cutoff:
                        job.state = "FAILED"
                        job.message = "desktop agent disconnected during HLS job"
                        now_text = cutoff.replace(microsecond=0).isoformat()
                        job.updated_at = now_text
                        if not str(job.started_at or "").strip():
                            job.started_at = now_text
                        job.finished_at = now_text
                        job.connection_lost_at = None
                        self._telemetry.reaped_hls_job_count += 1
                        self._record_reap_reason_locked("desktop agent disconnected during HLS job")
                        expired_hls_job_ids.append(job.job_id)
                        continue
                if _coerce_utc_datetime(job.expires_at) > cutoff:
                    continue
                job.state = "CANCELLED"
                job.message = "desktop agent HLS job expired"
                now_text = cutoff.replace(microsecond=0).isoformat()
                job.updated_at = now_text
                if not str(job.started_at or "").strip():
                    job.started_at = now_text
                job.finished_at = now_text
                job.connection_lost_at = None
                self._enqueue_command_locked(
                    job.agent_id,
                    {
                        "type": "job.cancel",
                        "jobId": job.job_id,
                        "reason": "desktop agent HLS job expired",
                    },
                )
                self._telemetry.reaped_hls_job_count += 1
                self._record_reap_reason_locked("desktop agent HLS job expired")
                expired_hls_job_ids.append(job.job_id)
        return {
            "expiredStreamIds": tuple(expired_stream_ids),
            "expiredProbeIds": tuple(expired_probe_ids),
            "expiredHlsJobIds": tuple(expired_hls_job_ids),
        }

    def snapshot_state(
        self,
        *,
        include_details: bool = False,
        max_recent_hls_jobs: int = 20,
    ) -> dict[str, Any]:
        with self._guard:
            connected_agent_ids = tuple(sorted(self._connections))
            queued_command_count = sum(connection.pending_commands.qsize() for connection in self._connections.values())
            active_stream_count = sum(1 for session in self._stream_sessions.values() if session.terminal is None)
            terminal_stream_count = sum(1 for session in self._stream_sessions.values() if session.terminal is not None)
            pending_probe_count = sum(1 for probe in self._probe_requests.values() if not probe.result_ready.is_set())
            hls_jobs_by_state: dict[str, int] = {}
            hls_job_reason_counts: dict[str, int] = {}
            for job in self._hls_jobs.values():
                hls_jobs_by_state[job.state] = hls_jobs_by_state.get(job.state, 0) + 1
                reason = str(job.message or "").strip()
                if job.state in {"FAILED", "CANCELLED"} and reason:
                    hls_job_reason_counts[reason] = hls_job_reason_counts.get(reason, 0) + 1
            active_hls_job_count = sum(
                1 for job in self._hls_jobs.values() if job.state not in {"COMPLETED", "FAILED", "CANCELLED"}
            )
            hls_cache_request_count = self._telemetry.hls_cache_hit_count + self._telemetry.hls_cache_miss_count
            payload: dict[str, Any] = {
                "connectedAgentCount": len(connected_agent_ids),
                "connectedAgentIds": connected_agent_ids,
                "queuedCommandCount": queued_command_count,
                "streamSessionCount": len(self._stream_sessions),
                "activeStreamCount": active_stream_count,
                "terminalStreamCount": terminal_stream_count,
                "probeRequestCount": len(self._probe_requests),
                "pendingProbeCount": pending_probe_count,
                "hlsJobCount": len(self._hls_jobs),
                "activeHlsJobCount": active_hls_job_count,
                "hlsJobsByState": dict(sorted(hls_jobs_by_state.items())),
                "hlsJobReasonCounts": dict(sorted(hls_job_reason_counts.items())),
                "hlsCacheRequestCount": hls_cache_request_count,
                "hlsCacheHitCount": self._telemetry.hls_cache_hit_count,
                "hlsCacheMissCount": self._telemetry.hls_cache_miss_count,
                "hlsCacheHitRate": (
                    round(self._telemetry.hls_cache_hit_count / hls_cache_request_count, 4)
                    if hls_cache_request_count > 0
                    else None
                ),
                "hlsArtifactRequestCount": self._telemetry.hls_artifact_request_count,
                "hlsArtifactBytesServed": self._telemetry.hls_artifact_bytes_served,
                "reapedStreamCount": self._telemetry.reaped_stream_count,
                "reapedProbeCount": self._telemetry.reaped_probe_count,
                "reapedHlsJobCount": self._telemetry.reaped_hls_job_count,
                "reapReasonCounts": dict(sorted(self._telemetry.reap_reason_counts.items())),
                "lastReapedAt": self._telemetry.last_reaped_at,
                "config": {
                    "probeTimeoutSeconds": self._config.probe_timeout_seconds,
                    "streamHeaderTimeoutSeconds": self._config.stream_header_timeout_seconds,
                    "streamIdleTimeoutSeconds": self._config.stream_idle_timeout_seconds,
                    "streamDisconnectGraceSeconds": self._stream_disconnect_grace_seconds,
                    "hlsDisconnectGraceSeconds": self._hls_disconnect_grace_seconds,
                    "maxConcurrentStreamsPerAgent": self._config.max_concurrent_streams_per_agent,
                    "maxConcurrentViewersPerUser": self._config.max_concurrent_viewers_per_user,
                },
            }
            if not include_details:
                return payload

            agent_activity: dict[str, dict[str, Any]] = {}
            for agent_id, connection in self._connections.items():
                agent_activity[str(agent_id)] = {
                    "agentId": str(agent_id),
                    "connected": True,
                    "queuedCommandCount": connection.pending_commands.qsize(),
                    "activeStreamCount": 0,
                    "pendingProbeCount": 0,
                    "activeHlsJobCount": 0,
                    "hlsJobCount": 0,
                    "hlsJobsByState": {},
                    "hlsTerminalReasonCounts": {},
                }

            for session in self._stream_sessions.values():
                item = agent_activity.setdefault(
                    session.agent_id,
                    {
                        "agentId": session.agent_id,
                        "connected": False,
                        "queuedCommandCount": 0,
                        "activeStreamCount": 0,
                        "pendingProbeCount": 0,
                        "activeHlsJobCount": 0,
                        "hlsJobCount": 0,
                        "hlsJobsByState": {},
                        "hlsTerminalReasonCounts": {},
                    },
                )
                if session.terminal is None:
                    item["activeStreamCount"] += 1

            for probe in self._probe_requests.values():
                item = agent_activity.setdefault(
                    probe.agent_id,
                    {
                        "agentId": probe.agent_id,
                        "connected": False,
                        "queuedCommandCount": 0,
                        "activeStreamCount": 0,
                        "pendingProbeCount": 0,
                        "activeHlsJobCount": 0,
                        "hlsJobCount": 0,
                        "hlsJobsByState": {},
                        "hlsTerminalReasonCounts": {},
                    },
                )
                if not probe.result_ready.is_set():
                    item["pendingProbeCount"] += 1

            recent_hls_jobs = sorted(
                self._hls_jobs.values(),
                key=lambda job: (_coerce_utc_datetime(job.created_at), str(job.job_id)),
                reverse=True,
            )[: max(1, int(max_recent_hls_jobs))]
            for job in self._hls_jobs.values():
                item = agent_activity.setdefault(
                    job.agent_id,
                    {
                        "agentId": job.agent_id,
                        "connected": False,
                        "queuedCommandCount": 0,
                        "activeStreamCount": 0,
                        "pendingProbeCount": 0,
                        "activeHlsJobCount": 0,
                        "hlsJobCount": 0,
                        "hlsJobsByState": {},
                        "hlsTerminalReasonCounts": {},
                    },
                )
                item["hlsJobCount"] += 1
                hls_jobs_by_state_for_agent = item["hlsJobsByState"]
                hls_jobs_by_state_for_agent[job.state] = hls_jobs_by_state_for_agent.get(job.state, 0) + 1
                if job.state not in {"COMPLETED", "FAILED", "CANCELLED"}:
                    item["activeHlsJobCount"] += 1
                reason = str(job.message or "").strip()
                if job.state in {"FAILED", "CANCELLED"} and reason:
                    reason_counts = item["hlsTerminalReasonCounts"]
                    reason_counts[reason] = reason_counts.get(reason, 0) + 1

            payload["agentActivity"] = [
                agent_activity[agent_id]
                for agent_id in sorted(agent_activity)
            ]
            payload["recentHlsJobs"] = [
                {
                    "jobId": job.job_id,
                    "cacheKey": job.cache_key,
                    "agentId": job.agent_id,
                    "projectId": job.project_id,
                    "instanceId": job.instance_id,
                    "relativePath": job.relative_path,
                    "profile": dict(job.profile),
                    "createdAt": job.created_at,
                    "updatedAt": job.updated_at,
                    "expiresAt": job.expires_at,
                    "state": job.state,
                    "message": job.message,
                    "startedAt": job.started_at,
                    "finishedAt": job.finished_at,
                    "lastArtifactAt": job.last_artifact_at,
                    "connectionLostAt": job.connection_lost_at,
                    "artifactCount": int(job.artifact_count),
                    "artifactBytes": int(job.artifact_bytes),
                }
                for job in recent_hls_jobs
            ]
            return payload

    def append_stream_chunk(
        self,
        stream_id: str,
        *,
        agent_id: str,
        content: bytes,
        content_type: str,
        file_size: int | None,
        range_start: int | None,
        range_end: int | None,
        is_final: bool,
    ) -> None:
        with self._guard:
            session = self._stream_sessions.get(str(stream_id))
            if session is None:
                raise DesktopAgentStreamNotFoundError(f"desktop agent stream session not found: {stream_id}")
            if session.agent_id != str(agent_id):
                raise PermissionError("stream session agent mismatch")
            if session.terminal is not None:
                raise DesktopAgentStreamClosedError(str(session.terminal.message or "desktop agent stream session is closed"))
            if session.headers is None:
                session.headers = _StreamHeaders(
                    content_type=str(content_type),
                    file_size=None if file_size is None else int(file_size),
                    range_start=None if range_start is None else int(range_start),
                    range_end=None if range_end is None else int(range_end),
                )
                session.headers_ready.set()
            session.last_activity_monotonic = time.monotonic()
            session.connection_lost_at = None
            if content:
                session.chunk_queue.put(bytes(content))
            if is_final:
                self._close_session_locked(session, kind="completed")

    async def wait_for_stream_headers(self, stream_id: str, timeout_seconds: float | None = None) -> _StreamHeaders:
        session = self.get_stream_session(stream_id)
        timeout = session.headers_wait_timeout_seconds if timeout_seconds is None else max(0.0, float(timeout_seconds))
        deadline = time.monotonic() + timeout
        while True:
            remaining = max(0.0, deadline - time.monotonic())
            if self._fail_stream_after_disconnect_grace(stream_id):
                raise DesktopAgentStreamClosedError("desktop agent disconnected during relay")
            is_ready = await asyncio.to_thread(session.headers_ready.wait, min(0.25, remaining))
            if is_ready:
                if session.headers is None:
                    raise self._terminal_error(session.terminal)
                return session.headers
            if remaining <= 0:
                self.cancel_stream_session(stream_id, reason="desktop agent stream headers timed out", notify_agent=True)
                raise DesktopAgentStreamTimeoutError("desktop agent stream headers timed out")

    async def iter_stream_content(self, stream_id: str):
        session = self.get_stream_session(stream_id)
        while True:
            idle_remaining = session.idle_timeout_seconds - max(0.0, time.monotonic() - session.last_activity_monotonic)
            if idle_remaining <= 0:
                self.cancel_stream_session(stream_id, reason="desktop agent stream became idle", notify_agent=True)
                raise DesktopAgentStreamTimeoutError("desktop agent stream became idle")
            try:
                item = await asyncio.to_thread(session.chunk_queue.get, True, min(0.25, idle_remaining))
            except queue.Empty:
                if self._fail_stream_after_disconnect_grace(stream_id):
                    raise DesktopAgentStreamClosedError("desktop agent disconnected during relay")
                continue
            if isinstance(item, _StreamTerminal):
                if item.kind == "completed":
                    break
                raise self._terminal_error(item)
            if not item:
                break
            yield item

    def release_stream_session(self, stream_id: str) -> None:
        with self._guard:
            self._stream_sessions.pop(str(stream_id), None)
