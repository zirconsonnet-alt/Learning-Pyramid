from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.system.desktop_agent_runtime import (
    DesktopAgentProbeClosedError,
    DesktopAgentRelayRuntimeConfig,
    DesktopAgentRuntime,
    DesktopAgentStreamClosedError,
    DesktopAgentStreamTimeoutError,
)


def _utc_text(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def test_desktop_agent_runtime_snapshot_reports_current_counters() -> None:
    runtime = DesktopAgentRuntime(
        DesktopAgentRelayRuntimeConfig(
            probe_timeout_seconds=15.0,
            stream_header_timeout_seconds=30.0,
            stream_idle_timeout_seconds=15.0,
            max_concurrent_streams_per_agent=2,
            max_concurrent_viewers_per_user=3,
        )
    )
    runtime.register_connection("agent_123", object())  # type: ignore[arg-type]
    runtime.create_stream_session(
        agent_id="agent_123",
        user_id="user_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=120,
    )
    runtime.create_probe_request(
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
    )
    runtime.create_or_get_hls_job(
        cache_key="cache_123",
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mkv",
        profile={"heightMax": 720},
    )

    snapshot = runtime.snapshot_state()

    assert snapshot["connectedAgentCount"] == 1
    assert snapshot["connectedAgentIds"] == ("agent_123",)
    assert snapshot["activeStreamCount"] == 1
    assert snapshot["pendingProbeCount"] == 1
    assert snapshot["activeHlsJobCount"] == 1
    assert snapshot["hlsJobsByState"] == {"OPENING": 1}
    assert snapshot["config"]["maxConcurrentStreamsPerAgent"] == 2
    assert snapshot["config"]["maxConcurrentViewersPerUser"] == 3
    assert snapshot["config"]["streamDisconnectGraceSeconds"] == 10.0
    assert snapshot["config"]["hlsDisconnectGraceSeconds"] == 30.0


def test_desktop_agent_runtime_reconnect_preserves_pending_commands_for_current_socket() -> None:
    runtime = DesktopAgentRuntime()
    old_socket = object()
    new_socket = object()

    runtime.register_connection("agent_123", old_socket)  # type: ignore[arg-type]
    runtime.enqueue_command("agent_123", {"type": "probe.request", "requestId": "probe_123"})

    runtime.register_connection("agent_123", new_socket)  # type: ignore[arg-type]

    assert runtime.drain_commands("agent_123", old_socket) == []  # type: ignore[arg-type]
    assert runtime.drain_commands("agent_123", new_socket) == [  # type: ignore[arg-type]
        {"type": "probe.request", "requestId": "probe_123"}
    ]


def test_desktop_agent_runtime_snapshot_can_include_agent_activity_and_recent_jobs() -> None:
    runtime = DesktopAgentRuntime()
    runtime.register_connection("agent_123", object())  # type: ignore[arg-type]
    runtime.enqueue_command("agent_123", {"type": "stream.cancel", "streamId": "stream_x"})
    runtime.create_stream_session(
        agent_id="agent_123",
        user_id="user_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=120,
    )
    runtime.create_probe_request(
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
    )
    job, _ = runtime.create_or_get_hls_job(
        cache_key="cache_123",
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mkv",
        profile={"heightMax": 720},
    )
    runtime.update_hls_job_state(job.job_id, agent_id="agent_123", state="FAILED", message="ffmpeg exited 1")

    snapshot = runtime.snapshot_state(include_details=True, max_recent_hls_jobs=5)

    assert snapshot["agentActivity"] == [
        {
            "agentId": "agent_123",
            "connected": True,
            "queuedCommandCount": 1,
            "activeStreamCount": 1,
            "pendingProbeCount": 1,
            "activeHlsJobCount": 0,
            "hlsJobCount": 1,
            "hlsJobsByState": {"FAILED": 1},
            "hlsTerminalReasonCounts": {"ffmpeg exited 1": 1},
        }
    ]
    assert snapshot["recentHlsJobs"] == [
        {
            "jobId": job.job_id,
            "cacheKey": "cache_123",
            "agentId": "agent_123",
            "projectId": "proj_123",
            "instanceId": "inst_123",
            "relativePath": "lesson-01.mkv",
            "profile": {"heightMax": 720},
            "createdAt": job.created_at,
            "updatedAt": job.updated_at,
            "expiresAt": job.expires_at,
            "state": "FAILED",
            "message": "ffmpeg exited 1",
            "startedAt": job.started_at,
            "finishedAt": job.finished_at,
            "lastArtifactAt": job.last_artifact_at,
            "connectionLostAt": None,
            "artifactCount": 0,
            "artifactBytes": 0,
        }
    ]


def test_desktop_agent_runtime_applies_hls_disconnect_grace_before_failing_job() -> None:
    runtime = DesktopAgentRuntime()
    runtime.register_connection("agent_123", object())  # type: ignore[arg-type]
    job, _ = runtime.create_or_get_hls_job(
        cache_key="cache_disconnect_123",
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mkv",
        profile={"heightMax": 720},
    )
    runtime.update_hls_job_state(job.job_id, agent_id="agent_123", state="RUNNING")

    runtime.unregister_connection("agent_123")
    current = runtime.get_hls_job(job.job_id)
    assert current.state == "RUNNING"
    assert current.connection_lost_at is not None

    disconnected_at = datetime.fromisoformat(str(current.connection_lost_at)).astimezone(timezone.utc)
    before_grace = disconnected_at + timedelta(seconds=20)
    reaped_before_grace = runtime.reap_expired(now=before_grace)
    assert reaped_before_grace["expiredHlsJobIds"] == ()
    assert runtime.get_hls_job(job.job_id).state == "RUNNING"

    after_grace = disconnected_at + timedelta(seconds=31)
    reaped_after_grace = runtime.reap_expired(now=after_grace)
    assert reaped_after_grace["expiredHlsJobIds"] == (job.job_id,)
    failed = runtime.get_hls_job(job.job_id)
    assert failed.state == "FAILED"
    assert failed.message == "desktop agent disconnected during HLS job"
    assert failed.finished_at is not None


def test_desktop_agent_runtime_allows_stream_headers_after_connection_loss() -> None:
    runtime = DesktopAgentRuntime()
    runtime.register_connection("agent_123", object())  # type: ignore[arg-type]
    session = runtime.create_stream_session(
        agent_id="agent_123",
        user_id="user_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=60,
    )

    runtime.unregister_connection("agent_123")
    runtime.append_stream_chunk(
        session.stream_id,
        agent_id="agent_123",
        content=b"ab",
        content_type="video/mp4",
        file_size=4,
        range_start=0,
        range_end=3,
        is_final=False,
    )

    headers = asyncio.run(runtime.wait_for_stream_headers(session.stream_id, timeout_seconds=0.1))

    assert headers.content_type == "video/mp4"
    assert headers.file_size == 4
    assert headers.range_start == 0
    assert headers.range_end == 3
    assert runtime.get_stream_session(session.stream_id).connection_lost_at is None


def test_desktop_agent_runtime_fails_stream_after_disconnect_grace() -> None:
    runtime = DesktopAgentRuntime()
    runtime.register_connection("agent_123", object())  # type: ignore[arg-type]
    session = runtime.create_stream_session(
        agent_id="agent_123",
        user_id="user_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=60,
    )

    runtime.unregister_connection("agent_123")
    runtime.get_stream_session(session.stream_id).connection_lost_at = _utc_text(
        datetime.now(timezone.utc) - timedelta(seconds=11)
    )

    with pytest.raises(DesktopAgentStreamClosedError, match="desktop agent disconnected during relay"):
        asyncio.run(runtime.wait_for_stream_headers(session.stream_id, timeout_seconds=1))


def test_desktop_agent_runtime_reaps_expired_streams_probes_and_hls_jobs() -> None:
    runtime = DesktopAgentRuntime()
    runtime.register_connection("agent_123", object())  # type: ignore[arg-type]
    now = datetime(2026, 3, 11, 12, 0, 0, tzinfo=timezone.utc)

    stream = runtime.create_stream_session(
        agent_id="agent_123",
        user_id="user_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
        content_type="video/mp4",
        ttl_seconds=60,
    )
    probe = runtime.create_probe_request(
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mp4",
    )
    job, _ = runtime.create_or_get_hls_job(
        cache_key="cache_123",
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mkv",
        profile={"heightMax": 720},
    )

    runtime.get_stream_session(stream.stream_id).expires_at = _utc_text(now - timedelta(seconds=1))
    runtime._probe_requests[probe.request_id].expires_at = _utc_text(now - timedelta(seconds=1))
    runtime.get_hls_job(job.job_id).expires_at = _utc_text(now - timedelta(seconds=1))

    reaped = runtime.reap_expired(now=now)

    assert reaped == {
        "expiredStreamIds": (stream.stream_id,),
        "expiredProbeIds": (probe.request_id,),
        "expiredHlsJobIds": (job.job_id,),
    }

    with pytest.raises(DesktopAgentStreamTimeoutError, match="desktop agent stream session expired"):
        asyncio.run(runtime.wait_for_stream_headers(stream.stream_id, timeout_seconds=0))

    with pytest.raises(DesktopAgentProbeClosedError, match="desktop agent media probe expired"):
        asyncio.run(runtime.wait_for_probe_result(probe.request_id, timeout_seconds=0))

    drained = runtime.drain_commands("agent_123")
    assert [item["type"] for item in drained] == ["stream.cancel", "job.cancel"]
    assert drained[0]["streamId"] == stream.stream_id
    assert drained[1]["jobId"] == job.job_id

    snapshot = runtime.snapshot_state()
    assert snapshot["activeStreamCount"] == 0
    assert snapshot["pendingProbeCount"] == 0
    assert snapshot["activeHlsJobCount"] == 0
    assert snapshot["hlsJobsByState"]["CANCELLED"] == 1
    assert snapshot["reapedStreamCount"] == 1
    assert snapshot["reapedProbeCount"] == 1
    assert snapshot["reapedHlsJobCount"] == 1
    assert snapshot["reapReasonCounts"] == {
        "desktop agent HLS job expired": 1,
        "desktop agent media probe expired": 1,
        "desktop agent stream session expired": 1,
    }


def test_desktop_agent_runtime_tracks_hls_cache_telemetry() -> None:
    runtime = DesktopAgentRuntime()

    runtime.record_hls_cache_lookup(hit=False)
    runtime.record_hls_cache_lookup(hit=True)
    runtime.record_hls_cache_lookup(hit=True)
    runtime.record_hls_artifact_served(size_bytes=4096)
    runtime.record_hls_artifact_served(size_bytes=2048)

    snapshot = runtime.snapshot_state()

    assert snapshot["hlsCacheRequestCount"] == 3
    assert snapshot["hlsCacheHitCount"] == 2
    assert snapshot["hlsCacheMissCount"] == 1
    assert snapshot["hlsCacheHitRate"] == 0.6667
    assert snapshot["hlsArtifactRequestCount"] == 2
    assert snapshot["hlsArtifactBytesServed"] == 6144


def test_desktop_agent_runtime_tracks_hls_job_artifact_and_terminal_timestamps() -> None:
    runtime = DesktopAgentRuntime()
    job, _ = runtime.create_or_get_hls_job(
        cache_key="cache_abc",
        agent_id="agent_123",
        project_id="proj_123",
        instance_id="inst_123",
        relative_path="lesson-01.mkv",
        profile={"heightMax": 720},
    )

    runtime.update_hls_job_state(job.job_id, agent_id="agent_123", state="RUNNING")
    runtime.record_hls_job_artifact(job.job_id, size_bytes=1024)
    runtime.update_hls_job_state(job.job_id, agent_id="agent_123", state="COMPLETED")

    current = runtime.get_hls_job(job.job_id)

    assert current.started_at is not None
    assert current.finished_at is not None
    assert current.last_artifact_at is not None
    assert current.artifact_count == 1
    assert current.artifact_bytes == 1024
