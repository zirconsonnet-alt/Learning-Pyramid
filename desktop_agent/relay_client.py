from __future__ import annotations

import json
import shutil
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, RLock, Thread
from typing import Any, Callable
from urllib.parse import urlparse

import requests
import websocket

from desktop_agent.config_store import AgentConfig
from desktop_agent.errors import DesktopAgentTaskCancelled
from desktop_agent.local_diagnostics import collect_media_file_stat_details, resolve_media_tool_path
from desktop_agent.manifest_scan import scan_media_manifest
from desktop_agent.path_safety import resolve_agent_media_path
from desktop_agent.probe import probe_media_file
from desktop_agent.transcode import transcode_media_to_hls


def _http_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _ws_url(base_url: str, path: str) -> str:
    parsed = urlparse(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc or parsed.path
    base_path = parsed.path if parsed.netloc else ""
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{scheme}://{netloc}{base_path.rstrip('/')}{suffix}"


class DesktopAgentAuthExpired(RuntimeError):
    pass


def _agent_error_message(response: requests.Response) -> str:
    fallback = f"{response.status_code} Client Error: {response.reason} for url: {response.url}"
    try:
        payload = response.json()
    except ValueError:
        return fallback
    if not isinstance(payload, dict):
        return fallback
    error = payload.get("error")
    if not isinstance(error, dict):
        return fallback
    message = str(error.get("message") or "").strip()
    if not message:
        return fallback
    return f"{response.status_code} Client Error: {message} for url: {response.url}"


def _raise_for_agent_response(response: requests.Response) -> None:
    if response.status_code == 401:
        raise DesktopAgentAuthExpired("desktop agent authentication expired")
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise requests.HTTPError(_agent_error_message(response), response=response, request=response.request) from exc


def _http_error_means_stream_session_gone(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code not in {404, 409, 410}:
        return False
    message = str(exc).strip().lower()
    if "stream session" in message:
        return True
    request = getattr(exc, "request", None)
    request_url = str(getattr(request, "url", "") or getattr(response, "url", "")).lower()
    return "/stream-sessions/" in request_url


def _http_error_means_hls_job_gone(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code not in {404, 409, 410}:
        return False
    message = str(exc).strip().lower()
    if "hls job" in message:
        return True
    request = getattr(exc, "request", None)
    request_url = str(getattr(request, "url", "") or getattr(response, "url", "")).lower()
    return "/hls-jobs/" in request_url


def _is_websocket_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return True
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 401:
        return True
    return False


def _invalid_ws_message_preview(raw: object, *, limit: int = 160) -> str:
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8", errors="replace")
        except Exception:
            text = repr(raw)
    else:
        text = str(raw)
    sanitized = " ".join(text.split())
    if len(sanitized) > limit:
        return sanitized[: limit - 3] + "..."
    return sanitized


@dataclass
class _BackgroundTaskHandle:
    task_id: str
    cancel_event: Event
    thread: Thread


class RelayClient:
    def __init__(self, config: AgentConfig, *, stream_chunk_size_bytes: int = 256 * 1024) -> None:
        self.config = config
        self.http = requests.Session()
        self.http.headers.update({"Authorization": f"Bearer {config.agent_token}"})
        self._last_manifest_signature: str | None = None
        self._stream_chunk_size_bytes = max(1, int(stream_chunk_size_bytes))
        self._task_guard = RLock()
        self._ws_send_lock = Lock()
        self._stream_tasks: dict[str, _BackgroundTaskHandle] = {}
        self._hls_tasks: dict[str, _BackgroundTaskHandle] = {}
        self._task_errors: Queue[BaseException] = Queue()
        self._diagnostic_signatures: dict[str, str] = {}

    def set_agent_token(self, agent_token: str) -> None:
        self.config.agent_token = str(agent_token)
        self.http.headers.update({"Authorization": f"Bearer {self.config.agent_token}"})

    def pair(self, pairing_code: str) -> dict[str, Any]:
        response = requests.post(
            _http_url(self.config.server_url, "/api/desktop-agents/pair"),
            json={
                "pairingCode": pairing_code,
                "deviceName": self.config.device_name,
                "platform": self.config.platform,
                "appVersion": self.config.app_version,
            },
            timeout=30,
        )
        _raise_for_agent_response(response)
        return response.json()["data"]

    def refresh_tokens(self, refresh_token: str | None = None) -> dict[str, Any]:
        response = requests.post(
            _http_url(self.config.server_url, "/api/desktop-agents/refresh-token"),
            json={"refreshToken": str(refresh_token or self.config.refresh_token)},
            timeout=30,
        )
        _raise_for_agent_response(response)
        data = response.json()["data"]
        self.set_agent_token(str(data["agentToken"]))
        self.config.refresh_token = str(data["refreshToken"])
        return data

    def sync_manifest(self) -> dict[str, Any]:
        entries = scan_media_manifest(self.config.root_dir)
        signature = json.dumps(entries, ensure_ascii=False, separators=(",", ":"))
        if self._last_manifest_signature == signature:
            return {"unchanged": True}
        response = self.http.post(
            _http_url(self.config.server_url, "/api/desktop-agents/manifest-sync"),
            json={
                "projectId": self.config.project_id,
                "agentId": self.config.agent_id,
                "rootTitle": self.config.source_root_label,
                "entries": entries,
            },
            timeout=120,
        )
        _raise_for_agent_response(response)
        self._last_manifest_signature = signature
        return response.json()["data"]

    def report_diagnostic_event(
        self,
        *,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        project_id: str | None = None,
        instance_id: str | None = None,
        relative_path: str | None = None,
        raise_on_auth_expired: bool = False,
    ) -> bool:
        try:
            response = self.http.post(
                _http_url(self.config.server_url, "/api/desktop-agents/diagnostic-events"),
                json={
                    "level": str(level),
                    "category": str(category),
                    "eventType": str(event_type),
                    "message": str(message),
                    "details": dict(details or {}),
                    "projectId": project_id,
                    "instanceId": instance_id,
                    "relativePath": relative_path,
                    "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                },
                timeout=15,
            )
            _raise_for_agent_response(response)
            return True
        except DesktopAgentAuthExpired:
            if raise_on_auth_expired:
                raise
            return False
        except Exception:
            return False

    def _upload_stream_chunk(
        self,
        *,
        stream_id: str,
        chunk: bytes,
        content_type: str,
        file_size: int,
        range_start: int,
        range_end: int,
        is_final: bool,
    ) -> None:
        response = self.http.put(
            _http_url(self.config.server_url, f"/api/desktop-agents/stream-sessions/{stream_id}/chunks"),
            headers={
                "X-Content-Type": content_type,
                "X-File-Size": str(file_size),
                "X-Range-Start": str(range_start),
                "X-Range-End": str(range_end),
                "X-Is-Final": "true" if is_final else "false",
            },
            data=chunk,
            timeout=120,
        )
        _raise_for_agent_response(response)

    def _upload_hls_artifact(self, *, job_id: str, artifact_path: str, content: bytes) -> None:
        response = self.http.put(
            _http_url(self.config.server_url, f"/api/desktop-agents/hls-jobs/{job_id}/artifacts/{artifact_path}"),
            data=content,
            timeout=300,
        )
        _raise_for_agent_response(response)

    def _report_hls_job_state_http(self, *, job_id: str, state: str, message: str | None = None) -> None:
        response = self.http.put(
            _http_url(self.config.server_url, f"/api/desktop-agents/hls-jobs/{job_id}/state"),
            json={
                "state": str(state),
                "message": None if message is None else str(message),
            },
            timeout=30,
        )
        _raise_for_agent_response(response)

    def _send_ws_json(self, ws: websocket.WebSocket, payload: dict[str, Any]) -> None:
        with self._ws_send_lock:
            ws.send(json.dumps(payload))

    def _record_background_error(self, exc: BaseException) -> None:
        self._task_errors.put(exc)

    def _raise_background_error_if_any(self) -> None:
        try:
            exc = self._task_errors.get_nowait()
        except Empty:
            return
        raise exc

    def _task_handle(self, kind: str, task_id: str) -> _BackgroundTaskHandle | None:
        with self._task_guard:
            tasks = self._stream_tasks if kind == "stream" else self._hls_tasks
            return tasks.get(str(task_id))

    def _active_task_counts(self) -> dict[str, int]:
        with self._task_guard:
            return {
                "stream": sum(1 for item in self._stream_tasks.values() if item.thread.is_alive()),
                "hls": sum(1 for item in self._hls_tasks.values() if item.thread.is_alive()),
            }

    def _spawn_task(self, kind: str, task_id: str, runner: Callable[[Event], None]) -> None:
        cancel_event = Event()

        def _target() -> None:
            try:
                runner(cancel_event)
            except DesktopAgentTaskCancelled:
                return
            except DesktopAgentAuthExpired as exc:
                self._record_background_error(exc)
            except Exception as exc:
                self._record_background_error(exc)
            finally:
                with self._task_guard:
                    tasks = self._stream_tasks if kind == "stream" else self._hls_tasks
                    current = tasks.get(task_id)
                    if current is not None and current.thread is thread:
                        tasks.pop(task_id, None)

        thread = Thread(target=_target, name=f"desktop-agent-{kind}-{task_id}", daemon=True)
        with self._task_guard:
            tasks = self._stream_tasks if kind == "stream" else self._hls_tasks
            existing = tasks.get(task_id)
            if existing is not None:
                existing.cancel_event.set()
            tasks[task_id] = _BackgroundTaskHandle(task_id=task_id, cancel_event=cancel_event, thread=thread)
        thread.start()

    @staticmethod
    def _http_error_means_cancelled(exc: Exception, cancel_event: Event) -> bool:
        if not cancel_event.is_set():
            return False
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None) in {404, 409, 410}

    def _cancel_task(self, kind: str, task_id: str) -> None:
        handle = self._task_handle(kind, task_id)
        if handle is None:
            return
        handle.cancel_event.set()

    def _report_diagnostic_once(
        self,
        *,
        signature_key: str,
        signature_value: str,
        level: str,
        category: str,
        event_type: str,
        message: str,
        details: dict[str, Any] | None = None,
        project_id: str | None = None,
        instance_id: str | None = None,
        relative_path: str | None = None,
    ) -> bool:
        previous = self._diagnostic_signatures.get(signature_key)
        if previous == signature_value:
            return False
        reported = self.report_diagnostic_event(
            level=level,
            category=category,
            event_type=event_type,
            message=message,
            details=details,
            project_id=project_id,
            instance_id=instance_id,
            relative_path=relative_path,
        )
        if reported:
            self._diagnostic_signatures[signature_key] = signature_value
        return reported

    def _report_local_environment_diagnostics(self) -> None:
        root_path = Path(self.config.root_dir).expanduser()
        root_exists = root_path.exists()
        root_is_dir = root_path.is_dir() if root_exists else False
        root_details = {
            "rootDir": str(root_path),
            "rootDirExists": root_exists,
            "rootDirIsDirectory": root_is_dir,
            "sourceRootLabel": self.config.source_root_label,
        }
        root_signature = json.dumps(root_details, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if not root_exists or not root_is_dir:
            self._report_diagnostic_once(
                signature_key="root_dir_unavailable",
                signature_value=root_signature,
                level="error",
                category="service",
                event_type="root_dir_unavailable",
                message="desktop agent root directory is unavailable",
                details=root_details,
                project_id=self.config.project_id,
            )

        ffprobe_path = resolve_media_tool_path("ffprobe")
        ffmpeg_path = resolve_media_tool_path("ffmpeg")
        tool_checks = (
            ("ffprobe_missing", "probe", ffprobe_path, "ffprobe executable is not available"),
            ("ffmpeg_missing", "hls", ffmpeg_path, "ffmpeg executable is not available"),
        )
        for event_type, category, resolved_path, message in tool_checks:
            if resolved_path:
                continue
            details = {"rootDir": str(root_path), "toolPath": resolved_path}
            signature = json.dumps(details, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            self._report_diagnostic_once(
                signature_key=event_type,
                signature_value=signature,
                level="warning",
                category=category,
                event_type=event_type,
                message=message,
                details=details,
                project_id=self.config.project_id,
            )

    def _probe_failure_payload(self, *, relative_path: str, error: str) -> dict[str, Any]:
        try:
            file_path = resolve_agent_media_path(self.config.root_dir, relative_path)
        except Exception:
            file_path = None
        details = {} if file_path is None else collect_media_file_stat_details(file_path)
        return {
            "container": Path(relative_path).suffix.lower().lstrip(".") or "unknown",
            "videoCodec": None,
            "audioCodec": None,
            "durationMs": None,
            "bitrateBps": None,
            "width": None,
            "height": None,
            "fps": None,
            "audioChannels": None,
            "audioSampleRate": None,
            "videoStreamCount": 0,
            "audioStreamCount": 0,
            "subtitleStreamCount": 0,
            "sizeBytes": details.get("sizeBytes"),
            "modifiedAt": details.get("modifiedAt"),
            "ffprobePath": resolve_media_tool_path("ffprobe"),
            "error": str(error),
        }

    def _cancel_all_tasks(self) -> None:
        self._cancel_tasks("stream", "hls")

    def _cancel_tasks(self, *kinds: str) -> None:
        selected_kinds = {str(kind) for kind in kinds}
        with self._task_guard:
            handles: list[_BackgroundTaskHandle] = []
            if "stream" in selected_kinds:
                handles.extend(self._stream_tasks.values())
            if "hls" in selected_kinds:
                handles.extend(self._hls_tasks.values())
        for handle in handles:
            handle.cancel_event.set()

    def _join_all_tasks(self, timeout_seconds: float = 2.0) -> None:
        self._join_tasks("stream", "hls", timeout_seconds=timeout_seconds)

    def _join_tasks(self, *kinds: str, timeout_seconds: float = 2.0) -> None:
        selected_kinds = {str(kind) for kind in kinds}
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        with self._task_guard:
            handles: list[_BackgroundTaskHandle] = []
            if "stream" in selected_kinds:
                handles.extend(self._stream_tasks.values())
            if "hls" in selected_kinds:
                handles.extend(self._hls_tasks.values())
        for handle in handles:
            remaining = max(0.0, deadline - time.monotonic())
            handle.thread.join(timeout=remaining)

    def _handle_stream_open(self, payload: dict[str, Any]) -> None:
        relative_path = str(payload["relativePath"])
        stream_id = str(payload["streamId"])
        content_type = str(payload.get("contentType") or "application/octet-stream")
        range_start_raw = payload.get("rangeStart")
        range_end_raw = payload.get("rangeEnd")

        def _run(cancel_event: Event) -> None:
            file_path = resolve_agent_media_path(self.config.root_dir, relative_path)
            file_size = int(file_path.stat().st_size)

            start = 0 if range_start_raw is None else max(0, int(range_start_raw))
            end = file_size - 1 if range_end_raw is None else min(file_size - 1, int(range_end_raw))
            if end < start:
                raise RuntimeError(f"invalid range: {start}-{end}")

            try:
                with file_path.open("rb") as handle:
                    handle.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        if cancel_event.is_set():
                            raise DesktopAgentTaskCancelled("desktop agent stream cancelled")
                        current = handle.read(min(self._stream_chunk_size_bytes, remaining))
                        if not current:
                            break
                        remaining -= len(current)
                        try:
                            self._upload_stream_chunk(
                                stream_id=stream_id,
                                chunk=current,
                                content_type=content_type,
                                file_size=file_size,
                                range_start=start,
                                range_end=end,
                                is_final=remaining == 0,
                            )
                        except Exception as exc:
                            if self._http_error_means_cancelled(exc, cancel_event) or _http_error_means_stream_session_gone(exc):
                                raise DesktopAgentTaskCancelled("desktop agent stream cancelled") from exc
                            raise
            except DesktopAgentTaskCancelled:
                raise
            except Exception as exc:
                self.report_diagnostic_event(
                    level="error",
                    category="stream",
                    event_type="stream_open_failed",
                    message=str(exc),
                    details={"streamId": stream_id, "rangeStart": start, "rangeEnd": end},
                    project_id=self.config.project_id,
                    relative_path=relative_path,
                )
                raise

        self._spawn_task("stream", stream_id, _run)

    def _handle_stream_cancel(self, payload: dict[str, Any]) -> None:
        self._cancel_task("stream", str(payload.get("streamId", "")))

    def _handle_probe_request(self, ws: websocket.WebSocket, payload: dict[str, Any]) -> None:
        relative_path = str(payload["relativePath"])
        request_id = str(payload["requestId"])
        try:
            probe_payload = probe_media_file(self.config.root_dir, relative_path)
        except Exception as exc:
            fallback_payload = self._probe_failure_payload(relative_path=relative_path, error=str(exc))
            self.report_diagnostic_event(
                level="warning",
                category="probe",
                event_type="probe_failed",
                message=str(exc),
                details={
                    "requestId": request_id,
                    "ffprobePath": fallback_payload.get("ffprobePath"),
                    "sizeBytes": fallback_payload.get("sizeBytes"),
                    "modifiedAt": fallback_payload.get("modifiedAt"),
                },
                project_id=None if payload.get("projectId") is None else str(payload.get("projectId")),
                instance_id=None if payload.get("instanceId") is None else str(payload.get("instanceId")),
                relative_path=relative_path,
            )
            probe_payload = fallback_payload
        self._send_ws_json(
            ws,
            {
                "type": "probe.result",
                "requestId": request_id,
                "projectId": payload.get("projectId"),
                "instanceId": payload.get("instanceId"),
                "relativePath": relative_path,
                **probe_payload,
            },
        )

    def _handle_hls_start(self, ws: websocket.WebSocket, payload: dict[str, Any]) -> None:
        job_id = str(payload["jobId"])
        relative_path = str(payload["relativePath"])
        profile = dict(payload.get("profile") or {})

        def _run(cancel_event: Event) -> None:
            output_dir = None
            try:
                try:
                    self._report_hls_job_state_http(job_id=job_id, state="RUNNING")
                except Exception as exc:
                    if _http_error_means_hls_job_gone(exc):
                        raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled") from exc
                    raise
                output_dir, artifacts = transcode_media_to_hls(
                    self.config.root_dir,
                    relative_path,
                    height_max=int(profile.get("heightMax") or 720),
                    video_bitrate=str(profile.get("videoBitrate") or "1800k"),
                    audio_bitrate=str(profile.get("audioBitrate") or "128k"),
                    segment_seconds=int(profile.get("segmentSeconds") or 6),
                    cancel_event=cancel_event,
                )
                if cancel_event.is_set():
                    raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled")
                for artifact in artifacts:
                    if cancel_event.is_set():
                        raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled")
                    relative_artifact_path = artifact.relative_to(output_dir).as_posix()
                    try:
                        self._upload_hls_artifact(
                            job_id=job_id,
                            artifact_path=relative_artifact_path,
                            content=artifact.read_bytes(),
                        )
                    except Exception as exc:
                        if self._http_error_means_cancelled(exc, cancel_event) or _http_error_means_hls_job_gone(exc):
                            raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled") from exc
                        raise
                try:
                    self._report_hls_job_state_http(job_id=job_id, state="COMPLETED")
                except Exception as exc:
                    if _http_error_means_hls_job_gone(exc):
                        raise DesktopAgentTaskCancelled("desktop agent HLS job cancelled") from exc
                    raise
            except DesktopAgentTaskCancelled as exc:
                self.report_diagnostic_event(
                    level="warning",
                    category="hls",
                    event_type="hls_cancelled",
                    message=str(exc),
                    details={"jobId": job_id, "profile": profile},
                    project_id=self.config.project_id,
                    relative_path=relative_path,
                )
                try:
                    self._report_hls_job_state_http(job_id=job_id, state="CANCELLED", message=str(exc))
                except Exception as state_exc:
                    if not _http_error_means_hls_job_gone(state_exc):
                        raise
                raise
            except DesktopAgentAuthExpired:
                raise
            except Exception as exc:
                self.report_diagnostic_event(
                    level="error",
                    category="hls",
                    event_type="hls_failed",
                    message=str(exc),
                    details={"jobId": job_id, "profile": profile},
                    project_id=self.config.project_id,
                    relative_path=relative_path,
                )
                try:
                    self._report_hls_job_state_http(job_id=job_id, state="FAILED", message=str(exc))
                except Exception as state_exc:
                    if not _http_error_means_hls_job_gone(state_exc):
                        raise
                return
            finally:
                if output_dir is not None:
                    shutil.rmtree(output_dir, ignore_errors=True)

        self._spawn_task("hls", job_id, _run)

    def _handle_job_cancel(self, payload: dict[str, Any]) -> None:
        self._cancel_task("hls", str(payload.get("jobId", "")))

    def run_session(
        self,
        *,
        heartbeat_sec: int = 15,
        max_runtime_seconds: float | None = None,
        stop_event: Event | None = None,
        on_connected: Callable[[], None] | None = None,
    ) -> None:
        ws = None
        started_at = time.monotonic()
        cancel_stream_tasks = True
        cancel_hls_tasks = True
        try:
            self._report_local_environment_diagnostics()
            self.sync_manifest()
            try:
                ws = websocket.create_connection(
                    _ws_url(self.config.server_url, "/api/desktop-agents/ws"),
                    header=[f"Authorization: Bearer {self.config.agent_token}"],
                    timeout=5,
                )
            except Exception as exc:
                if _is_websocket_auth_error(exc):
                    raise DesktopAgentAuthExpired("desktop agent authentication expired") from exc
                raise
            ws.settimeout(1.0)
            _ = ws.recv()
            self._send_ws_json(
                ws,
                {
                    "type": "hello",
                    "agentId": self.config.agent_id,
                    "deviceName": self.config.device_name,
                    "appVersion": self.config.app_version,
                },
            )
            if on_connected is not None:
                on_connected()
            last_heartbeat_at = 0.0
            while True:
                self._raise_background_error_if_any()
                if stop_event is not None and stop_event.is_set():
                    self._cancel_tasks("stream", "hls")
                    return
                if max_runtime_seconds is not None and time.monotonic() - started_at >= max_runtime_seconds:
                    self._cancel_tasks("stream", "hls")
                    return
                now = time.time()
                if now - last_heartbeat_at >= heartbeat_sec:
                    try:
                        self.sync_manifest()
                    except DesktopAgentAuthExpired:
                        raise
                    except Exception as exc:
                        self.report_diagnostic_event(
                            level="warning",
                            category="manifest",
                            event_type="manifest_sync_failed",
                            message=str(exc),
                            details={"heartbeatSeconds": heartbeat_sec},
                            project_id=self.config.project_id,
                        )
                    self._send_ws_json(
                        ws,
                        {"type": "heartbeat", "at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())},
                    )
                    last_heartbeat_at = now
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except socket.timeout:
                    continue
                if raw is None:
                    raise RuntimeError("websocket closed")
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self.report_diagnostic_event(
                        level="warning",
                        category="service",
                        event_type="ws_invalid_message",
                        message="ignored invalid websocket payload",
                        details={
                            "payloadType": type(raw).__name__,
                            "payloadLength": len(raw) if isinstance(raw, (str, bytes, bytearray)) else None,
                            "payloadPreview": _invalid_ws_message_preview(raw),
                        },
                        project_id=self.config.project_id,
                    )
                    continue
                message_type = str(payload.get("type", ""))
                if message_type in {"connected", "hello.ack", "heartbeat.ack", "ignored"}:
                    continue
                if message_type == "probe.request":
                    self._handle_probe_request(ws, payload)
                    continue
                if message_type == "job.cancel":
                    self._handle_job_cancel(payload)
                    continue
                if message_type == "hls.start":
                    self._handle_hls_start(ws, payload)
                    continue
                if message_type == "stream.cancel":
                    self._handle_stream_cancel(payload)
                    continue
                if message_type == "stream.open":
                    self._handle_stream_open(payload)
                    continue
        except DesktopAgentAuthExpired:
            raise
        except Exception:
            if self._active_task_counts().get("stream", 0) > 0:
                cancel_stream_tasks = False
            if self._active_task_counts().get("hls", 0) > 0:
                cancel_hls_tasks = False
            raise
        finally:
            if cancel_stream_tasks:
                self._cancel_tasks("stream")
                self._join_tasks("stream")
            if cancel_hls_tasks:
                self._cancel_tasks("hls")
                self._join_tasks("hls")
            if ws is not None:
                try:
                    ws.close()
                except Exception:
                    pass

    def run_forever(self) -> None:
        heartbeat_sec = 15
        reconnect_delay_sec = 3
        while True:
            try:
                self.run_session(heartbeat_sec=heartbeat_sec)
            except KeyboardInterrupt:
                raise
            except DesktopAgentAuthExpired:
                raise
            except Exception:
                time.sleep(reconnect_delay_sec)
