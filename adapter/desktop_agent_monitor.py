from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from adapter.desktop_agent_metric_samples import (
    _bucket_start,
    current_desktop_agent_metric_sampling_config,
    persist_desktop_agent_metric_samples,
)
from adapter.mappers import desktop_agent_to_dto
from backend.models.enums import DesktopAgentStatus, MaterialSourceKind
from backend.models.desktop_agent_diagnostic_event import DesktopAgentDiagnosticEvent
from backend.models.desktop_agent_hls_job_audit import DesktopAgentHlsJobAudit
from backend.models.desktop_agent_metric_sample import DesktopAgentMetricSample
from backend.models.media_stream_session import MediaStreamSession
from backend.system.api import SystemAPI
from backend.system.auth_store import AuthStore
from backend.system.desktop_agent_presence import desktop_agent_connection_state, effective_desktop_agent_status
from backend.system.desktop_agent_runtime import DesktopAgentRuntime
from backend.system.runtime_features import current_runtime_features


def _coerce_utc_datetime(value: str | None) -> datetime:
    if not str(value or "").strip():
        return datetime.fromtimestamp(0, tz=timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _session_to_issue_dto(item: MediaStreamSession, project_title: str | None = None) -> dict[str, Any]:
    return {
        "streamId": item.stream_id,
        "projectId": item.project_id,
        "projectTitle": project_title,
        "instanceId": item.instance_id,
        "agentId": item.agent_id,
        "mode": item.mode,
        "status": item.status,
        "rangeStart": item.range_start,
        "rangeEnd": item.range_end,
        "bytesFromAgent": int(item.bytes_from_agent),
        "bytesToViewer": int(item.bytes_to_viewer),
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
        "expiresAt": item.expires_at,
        "finishedAt": item.finished_at,
        "failureReason": item.failure_reason,
    }


def _increment_counter(target: dict[str, int], key: str, delta: int = 1) -> None:
    normalized = str(key or "").strip() or "unknown"
    target[normalized] = target.get(normalized, 0) + max(0, int(delta))


def _normalize_optional_text(value: str | None, *, uppercase: bool = False) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    return normalized.upper() if uppercase else normalized


def _parse_hls_profile(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _parse_json_object(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _desktop_agent_device_key(*, device_name: str, platform: str) -> tuple[str, str]:
    return (str(device_name or "").strip().casefold(), str(platform or "").strip().casefold())


def _diagnostic_event_to_dto(item: DesktopAgentDiagnosticEvent) -> dict[str, Any]:
    return {
        "eventId": item.event_id,
        "agentId": item.agent_id,
        "projectId": item.project_id,
        "instanceId": item.instance_id,
        "relativePath": item.relative_path,
        "level": item.level,
        "category": item.category,
        "eventType": item.event_type,
        "message": item.message,
        "details": _parse_json_object(item.details),
        "createdAt": item.created_at,
    }


def _matches_diagnostic_query(item: DesktopAgentDiagnosticEvent, query: str | None) -> bool:
    normalized_query = _normalize_optional_text(query)
    if normalized_query is None:
        return True
    needle = normalized_query.casefold()
    haystacks = (
        item.event_id,
        item.agent_id,
        item.project_id,
        item.instance_id,
        item.relative_path,
        item.level,
        item.category,
        item.event_type,
        item.message,
        item.details,
    )
    return any(needle in str(value or "").casefold() for value in haystacks)


def list_user_desktop_agent_diagnostic_events(
    *,
    user_id: str,
    auth_store: AuthStore,
    diagnostic_since_hours: int = 24,
    project_id_set: set[str] | None = None,
    now: datetime | None = None,
    level: str | None = None,
    category: str | None = None,
    event_type: str | None = None,
    agent_id: str | None = None,
    project_id: str | None = None,
    query: str | None = None,
) -> list[DesktopAgentDiagnosticEvent]:
    effective_now = now or datetime.now(timezone.utc)
    visible_project_ids = (
        set(str(item) for item in auth_store.list_project_ids_for_user(user_id))
        if project_id_set is None
        else {str(item) for item in project_id_set}
    )
    normalized_project_id = _normalize_optional_text(project_id)
    if normalized_project_id is not None and normalized_project_id not in visible_project_ids:
        return []
    normalized_agent_id = _normalize_optional_text(agent_id)
    normalized_level = _normalize_optional_text(level, uppercase=True)
    normalized_category = _normalize_optional_text(category)
    normalized_event_type = _normalize_optional_text(event_type)
    since = (effective_now - timedelta(hours=max(1, int(diagnostic_since_hours)))).replace(microsecond=0).isoformat()
    events = auth_store.list_desktop_agent_diagnostic_events_for_user(user_id, since=since)
    filtered: list[DesktopAgentDiagnosticEvent] = []
    for item in events:
        item_project_id = None if item.project_id is None else str(item.project_id)
        if item_project_id is not None and item_project_id not in visible_project_ids:
            continue
        if normalized_project_id is not None and item_project_id != normalized_project_id:
            continue
        if normalized_agent_id is not None and str(item.agent_id) != normalized_agent_id:
            continue
        if normalized_level is not None and str(item.level).strip().upper() != normalized_level:
            continue
        if normalized_category is not None and str(item.category).strip().casefold() != normalized_category.casefold():
            continue
        if normalized_event_type is not None and str(item.event_type).strip().casefold() != normalized_event_type.casefold():
            continue
        if not _matches_diagnostic_query(item, query):
            continue
        filtered.append(item)
    return filtered


def list_user_desktop_agent_diagnostic_event_dtos(
    *,
    user_id: str,
    auth_store: AuthStore,
    diagnostic_since_hours: int = 24,
    limit: int | None = None,
    project_id_set: set[str] | None = None,
    now: datetime | None = None,
    level: str | None = None,
    category: str | None = None,
    event_type: str | None = None,
    agent_id: str | None = None,
    project_id: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    events = list_user_desktop_agent_diagnostic_events(
        user_id=user_id,
        auth_store=auth_store,
        diagnostic_since_hours=diagnostic_since_hours,
        project_id_set=project_id_set,
        now=now,
        level=level,
        category=category,
        event_type=event_type,
        agent_id=agent_id,
        project_id=project_id,
        query=query,
    )
    if limit is not None:
        events = events[: max(1, int(limit))]
    return [_diagnostic_event_to_dto(item) for item in events]


def _hls_job_audit_to_dto(item: DesktopAgentHlsJobAudit) -> dict[str, Any]:
    return {
        "jobId": item.job_id,
        "cacheKey": item.cache_key,
        "agentId": item.agent_id,
        "projectId": item.project_id,
        "instanceId": item.instance_id,
        "relativePath": item.relative_path,
        "profile": _parse_hls_profile(item.profile),
        "createdAt": item.created_at,
        "updatedAt": item.updated_at,
        "expiresAt": item.expires_at,
        "state": item.state,
        "message": item.message,
        "startedAt": item.started_at,
        "finishedAt": item.finished_at,
        "lastArtifactAt": item.last_artifact_at,
        "connectionLostAt": None,
        "artifactCount": int(item.artifact_count),
        "artifactBytes": int(item.artifact_bytes),
    }


def _empty_hls_window() -> dict[str, int]:
    return {
        "jobCount": 0,
        "completedCount": 0,
        "failedCount": 0,
        "cancelledCount": 0,
        "artifactBytes": 0,
    }


def _accumulate_hls_window(target: dict[str, int], *, state: str, artifact_bytes: int) -> None:
    target["jobCount"] += 1
    target["artifactBytes"] += max(0, int(artifact_bytes))
    if state == "COMPLETED":
        target["completedCount"] += 1
    elif state == "FAILED":
        target["failedCount"] += 1
    elif state == "CANCELLED":
        target["cancelledCount"] += 1


def _positive_delta(current: int, previous: int | None) -> int:
    if previous is None:
        return 0
    return max(0, int(current) - int(previous))


_TREND_DELTA_FIELDS = (
    "uploadBytes",
    "viewerBytes",
    "artifactBytes",
    "completedStreams",
    "failedStreams",
    "cancelledStreams",
    "completedHlsJobs",
    "failedHlsJobs",
    "cancelledHlsJobs",
)


def _empty_trend_window() -> dict[str, int]:
    return {
        "pointCount": 0,
        "uploadBytes": 0,
        "viewerBytes": 0,
        "artifactBytes": 0,
        "completedStreams": 0,
        "failedStreams": 0,
        "cancelledStreams": 0,
        "completedHlsJobs": 0,
        "failedHlsJobs": 0,
        "cancelledHlsJobs": 0,
        "peakActiveStreams": 0,
        "peakActiveHlsJobs": 0,
        "peakCacheBytes": 0,
        "latestCacheBytes": 0,
    }


def _zero_trend_point_deltas(point: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(point)
    for field_name in _TREND_DELTA_FIELDS:
        cloned[field_name] = 0
    return cloned


def _slice_trend_points(points: list[dict[str, Any]], *, cutoff: datetime) -> list[dict[str, Any]]:
    window = [dict(item) for item in points if _coerce_utc_datetime(str(item.get("bucketStart"))) >= cutoff]
    if window:
        window[0] = _zero_trend_point_deltas(window[0])
    return window


def _rollup_trend_points(points: list[dict[str, Any]], *, bucket_seconds: int) -> list[dict[str, Any]]:
    if not points:
        return []
    aggregated_by_bucket: dict[str, dict[str, Any]] = {}
    latest_seen_at: dict[str, datetime] = {}
    for item in points:
        bucket_start = _bucket_start(_coerce_utc_datetime(str(item.get("bucketStart"))), bucket_seconds).isoformat()
        current = aggregated_by_bucket.setdefault(
            bucket_start,
            {
                "bucketStart": bucket_start,
                "capturedAt": str(item.get("capturedAt")),
                "bucketSeconds": int(bucket_seconds),
                "activeStreamCount": 0,
                "activeHlsJobCount": 0,
                "cacheEntryCount": 0,
                "cacheBytes": 0,
                "uploadBytes": 0,
                "viewerBytes": 0,
                "artifactBytes": 0,
                "completedStreams": 0,
                "failedStreams": 0,
                "cancelledStreams": 0,
                "completedHlsJobs": 0,
                "failedHlsJobs": 0,
                "cancelledHlsJobs": 0,
            },
        )
        current["activeStreamCount"] = max(int(current["activeStreamCount"]), int(item.get("activeStreamCount", 0)))
        current["activeHlsJobCount"] = max(int(current["activeHlsJobCount"]), int(item.get("activeHlsJobCount", 0)))
        for field_name in _TREND_DELTA_FIELDS:
            current[field_name] = int(current.get(field_name, 0)) + int(item.get(field_name, 0))
        captured_at = _coerce_utc_datetime(str(item.get("capturedAt")))
        if bucket_start not in latest_seen_at or captured_at >= latest_seen_at[bucket_start]:
            latest_seen_at[bucket_start] = captured_at
            current["capturedAt"] = str(item.get("capturedAt"))
            current["cacheEntryCount"] = int(item.get("cacheEntryCount", 0))
            current["cacheBytes"] = int(item.get("cacheBytes", 0))
    return [aggregated_by_bucket[key] for key in sorted(aggregated_by_bucket.keys())]


def _summarize_trend_window(points: list[dict[str, Any]]) -> dict[str, int]:
    if not points:
        return _empty_trend_window()
    return {
        "pointCount": len(points),
        "uploadBytes": sum(int(item.get("uploadBytes", 0)) for item in points),
        "viewerBytes": sum(int(item.get("viewerBytes", 0)) for item in points),
        "artifactBytes": sum(int(item.get("artifactBytes", 0)) for item in points),
        "completedStreams": sum(int(item.get("completedStreams", 0)) for item in points),
        "failedStreams": sum(int(item.get("failedStreams", 0)) for item in points),
        "cancelledStreams": sum(int(item.get("cancelledStreams", 0)) for item in points),
        "completedHlsJobs": sum(int(item.get("completedHlsJobs", 0)) for item in points),
        "failedHlsJobs": sum(int(item.get("failedHlsJobs", 0)) for item in points),
        "cancelledHlsJobs": sum(int(item.get("cancelledHlsJobs", 0)) for item in points),
        "peakActiveStreams": max(int(item.get("activeStreamCount", 0)) for item in points),
        "peakActiveHlsJobs": max(int(item.get("activeHlsJobCount", 0)) for item in points),
        "peakCacheBytes": max(int(item.get("cacheBytes", 0)) for item in points),
        "latestCacheBytes": int(points[-1].get("cacheBytes", 0)),
    }


def _build_relay_trends(
    samples: list[DesktopAgentMetricSample],
    *,
    sample_bucket_seconds: int,
    retention_days: int,
    now: datetime,
) -> dict[str, Any]:
    if not samples:
        return {
            "sampleBucketSeconds": int(sample_bucket_seconds),
            "retentionDays": int(retention_days),
            "sampleCount": 0,
            "sampledProjectCount": 0,
            "latestCapturedAt": None,
            "historyStartAt": None,
            "windows": {
                "last6Hours": _empty_trend_window(),
                "lastDay": _empty_trend_window(),
                "last7Days": _empty_trend_window(),
                "last30Days": _empty_trend_window(),
            },
            "timelines": {
                "last6Hours": [],
                "lastDay": [],
                "last7Days": [],
                "last30Days": [],
            },
        }

    aggregated_by_bucket: dict[str, dict[str, Any]] = {}
    sampled_project_ids: set[str] = set()
    for item in samples:
        sampled_project_ids.add(str(item.project_id))
        bucket = aggregated_by_bucket.setdefault(
            str(item.bucket_start),
            {
                "bucketStart": str(item.bucket_start),
                "capturedAt": str(item.captured_at),
                "bucketSeconds": int(item.bucket_seconds),
                "bytesFromAgentTotal": 0,
                "bytesToViewerTotal": 0,
                "hlsArtifactBytesTotal": 0,
                "completedStreamCount": 0,
                "failedStreamCount": 0,
                "cancelledStreamCount": 0,
                "completedHlsJobCount": 0,
                "failedHlsJobCount": 0,
                "cancelledHlsJobCount": 0,
                "activeStreamCount": 0,
                "activeHlsJobCount": 0,
                "cacheBytes": 0,
                "cacheEntryCount": 0,
            },
        )
        if _coerce_utc_datetime(str(item.captured_at)) > _coerce_utc_datetime(str(bucket["capturedAt"])):
            bucket["capturedAt"] = str(item.captured_at)
        bucket["bucketSeconds"] = max(int(bucket["bucketSeconds"]), int(item.bucket_seconds))
        bucket["bytesFromAgentTotal"] += int(item.bytes_from_agent_total)
        bucket["bytesToViewerTotal"] += int(item.bytes_to_viewer_total)
        bucket["hlsArtifactBytesTotal"] += int(item.hls_artifact_bytes_total)
        bucket["completedStreamCount"] += int(item.completed_stream_count)
        bucket["failedStreamCount"] += int(item.failed_stream_count)
        bucket["cancelledStreamCount"] += int(item.cancelled_stream_count)
        bucket["completedHlsJobCount"] += int(item.completed_hls_job_count)
        bucket["failedHlsJobCount"] += int(item.failed_hls_job_count)
        bucket["cancelledHlsJobCount"] += int(item.cancelled_hls_job_count)
        bucket["activeStreamCount"] += int(item.active_stream_count)
        bucket["activeHlsJobCount"] += int(item.active_hls_job_count)
        bucket["cacheBytes"] += int(item.hls_cache_bytes)
        bucket["cacheEntryCount"] += int(item.hls_cache_entry_count)

    ordered_buckets = [aggregated_by_bucket[key] for key in sorted(aggregated_by_bucket.keys())]
    points: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for bucket in ordered_buckets:
        point = {
            "bucketStart": str(bucket["bucketStart"]),
            "capturedAt": str(bucket["capturedAt"]),
            "bucketSeconds": int(bucket["bucketSeconds"]),
            "activeStreamCount": int(bucket["activeStreamCount"]),
            "activeHlsJobCount": int(bucket["activeHlsJobCount"]),
            "cacheEntryCount": int(bucket["cacheEntryCount"]),
            "cacheBytes": int(bucket["cacheBytes"]),
            "uploadBytes": _positive_delta(int(bucket["bytesFromAgentTotal"]), None if previous is None else int(previous["bytesFromAgentTotal"])),
            "viewerBytes": _positive_delta(int(bucket["bytesToViewerTotal"]), None if previous is None else int(previous["bytesToViewerTotal"])),
            "artifactBytes": _positive_delta(int(bucket["hlsArtifactBytesTotal"]), None if previous is None else int(previous["hlsArtifactBytesTotal"])),
            "completedStreams": _positive_delta(int(bucket["completedStreamCount"]), None if previous is None else int(previous["completedStreamCount"])),
            "failedStreams": _positive_delta(int(bucket["failedStreamCount"]), None if previous is None else int(previous["failedStreamCount"])),
            "cancelledStreams": _positive_delta(int(bucket["cancelledStreamCount"]), None if previous is None else int(previous["cancelledStreamCount"])),
            "completedHlsJobs": _positive_delta(int(bucket["completedHlsJobCount"]), None if previous is None else int(previous["completedHlsJobCount"])),
            "failedHlsJobs": _positive_delta(int(bucket["failedHlsJobCount"]), None if previous is None else int(previous["failedHlsJobCount"])),
            "cancelledHlsJobs": _positive_delta(int(bucket["cancelledHlsJobCount"]), None if previous is None else int(previous["cancelledHlsJobCount"])),
        }
        points.append(point)
        previous = bucket

    last_6_hours = _slice_trend_points(points, cutoff=now - timedelta(hours=6))
    last_day = _slice_trend_points(points, cutoff=now - timedelta(days=1))
    last_7_days = _rollup_trend_points(_slice_trend_points(points, cutoff=now - timedelta(days=7)), bucket_seconds=3600)
    last_30_days = _rollup_trend_points(_slice_trend_points(points, cutoff=now - timedelta(days=30)), bucket_seconds=86400)
    latest_captured_at = None if not points else str(points[-1].get("capturedAt"))
    history_start_at = None if not points else str(points[0].get("bucketStart"))
    return {
        "sampleBucketSeconds": int(sample_bucket_seconds),
        "retentionDays": int(retention_days),
        "sampleCount": len(points),
        "sampledProjectCount": len(sampled_project_ids),
        "latestCapturedAt": latest_captured_at,
        "historyStartAt": history_start_at,
        "windows": {
            "last6Hours": _summarize_trend_window(last_6_hours),
            "lastDay": _summarize_trend_window(last_day),
            "last7Days": _summarize_trend_window(last_7_days),
            "last30Days": _summarize_trend_window(last_30_days),
        },
        "timelines": {
            "last6Hours": last_6_hours,
            "lastDay": last_day,
            "last7Days": last_7_days,
            "last30Days": last_30_days,
        },
    }


def collect_user_desktop_agent_monitor(
    *,
    user_id: str,
    auth_store: AuthStore,
    runtime: DesktopAgentRuntime,
    api: SystemAPI,
    recent_issue_limit: int = 12,
    recent_hls_job_limit: int = 12,
    recent_diagnostic_limit: int = 12,
    diagnostic_since_hours: int = 24,
    alert_since_hours: int = 1,
    diagnostic_level: str | None = None,
    diagnostic_category: str | None = None,
    diagnostic_event_type: str | None = None,
    diagnostic_agent_id: str | None = None,
    diagnostic_project_id: str | None = None,
    diagnostic_query: str | None = None,
) -> dict[str, Any]:
    features = current_runtime_features()
    sampling_config = current_desktop_agent_metric_sampling_config()
    now = datetime.now(timezone.utc)
    if features.app_mode != "hosted":
        return {
            "available": False,
            "projectCount": 0,
            "agentCount": 0,
            "bindingSummary": {
                "desktopAgentProjectCount": 0,
                "boundOnlineProjectCount": 0,
                "boundOfflineProjectCount": 0,
                "serverFsProjectCount": 0,
                "supersededBindingCount": 0,
            },
            "projectBindings": [],
            "agents": [],
            "streamSummary": {
                "sessionCount": 0,
                "activeSessionCount": 0,
                "failedSessionCount": 0,
                "cancelledSessionCount": 0,
                "completedSessionCount": 0,
                "bytesFromAgentTotal": 0,
                "bytesToViewerTotal": 0,
                "sessionsByStatus": {},
                "issueReasonCounts": {},
            },
            "recentIssues": [],
            "hlsSummary": {
                "jobCount": 0,
                "activeHlsJobCount": 0,
                "jobsByState": {},
                "issueReasonCounts": {},
                "activityWindows": {
                    "lastHour": _empty_hls_window(),
                    "lastDay": _empty_hls_window(),
                },
            },
            "recentHlsJobs": [],
            "diagnosticSummary": {
                "eventCount": 0,
                "errorCount": 0,
                "warningCount": 0,
                "eventsByCategory": {},
                "eventsByLevel": {},
                "eventsByType": {},
            },
            "recentDiagnostics": [],
            "alerts": [],
            "trends": {
                "sampleBucketSeconds": int(sampling_config.bucket_seconds),
                "retentionDays": int(sampling_config.retention_days),
                "sampleCount": 0,
                "sampledProjectCount": 0,
                "latestCapturedAt": None,
                "historyStartAt": None,
                "windows": {
                    "last6Hours": _empty_trend_window(),
                    "lastDay": _empty_trend_window(),
                    "last7Days": _empty_trend_window(),
                    "last30Days": _empty_trend_window(),
                },
                "timelines": {
                    "last6Hours": [],
                    "lastDay": [],
                    "last7Days": [],
                    "last30Days": [],
                },
            },
        }

    project_ids = tuple(str(item) for item in auth_store.list_project_ids_for_user(user_id))
    project_id_set = set(project_ids)
    project_items = [project for project in api.list_projects() if str(project.project_id) in project_id_set]
    project_titles = {
        str(project.project_id): project.title
        for project in project_items
    }
    project_bindings_by_id = {
        str(project.project_id): api.get_project_material_source_binding(project.project_id)
        for project in project_items
    }
    sampling_report = persist_desktop_agent_metric_samples(auth_store, now=now)
    trend_since = (now - timedelta(days=min(max(1, int(sampling_config.retention_days)), 30), hours=1)).replace(
        microsecond=0
    ).isoformat()
    trend_samples = [
        item
        for item in auth_store.list_all_desktop_agent_metric_samples(since=trend_since)
        if str(item.project_id) in project_id_set
    ]
    diagnostic_events = list_user_desktop_agent_diagnostic_events(
        user_id=user_id,
        auth_store=auth_store,
        project_id_set=project_id_set,
        now=now,
        diagnostic_since_hours=diagnostic_since_hours,
        level=diagnostic_level,
        category=diagnostic_category,
        event_type=diagnostic_event_type,
        agent_id=diagnostic_agent_id,
        project_id=diagnostic_project_id,
        query=diagnostic_query,
    )
    filtered_diagnostic_events: list[DesktopAgentDiagnosticEvent] = []
    for item in diagnostic_events:
        item_project_id = None if item.project_id is None else str(item.project_id)
        if item_project_id is None:
            filtered_diagnostic_events.append(item)
            continue
        binding = project_bindings_by_id.get(item_project_id)
        if binding is None:
            continue
        binding_source_kind = getattr(binding.source_kind, "value", str(binding.source_kind))
        if binding_source_kind != MaterialSourceKind.DESKTOP_AGENT_MANIFEST.value:
            continue
        bound_agent_id = None if binding.desktop_agent_id is None else str(binding.desktop_agent_id)
        if bound_agent_id and str(item.agent_id) != bound_agent_id:
            continue
        filtered_diagnostic_events.append(item)
    diagnostic_events = filtered_diagnostic_events

    agents = list(auth_store.list_desktop_agents_for_user(user_id))
    all_agents_by_id = {str(item.agent_id): item for item in agents}
    runtime_state = runtime.snapshot_state(
        include_details=True,
        max_recent_hls_jobs=max(20, int(recent_hls_job_limit) * 4),
    )
    activity_by_agent = {
        str(item["agentId"]): dict(item)
        for item in runtime_state.get("agentActivity", [])
    }
    sorted_agents = sorted(
        agents,
        key=lambda item: (
            1 if bool(activity_by_agent.get(str(item.agent_id), {}).get("connected", False)) else 0,
            _coerce_utc_datetime(item.paired_at),
            _coerce_utc_datetime(item.last_seen_at),
            str(item.agent_id),
        ),
        reverse=True,
    )
    canonical_agents_by_device: dict[tuple[str, str], Any] = {}
    visible_agents: list[Any] = []
    for agent in sorted_agents:
        device_key = _desktop_agent_device_key(device_name=agent.device_name, platform=agent.platform)
        if device_key in canonical_agents_by_device:
            continue
        canonical_agents_by_device[device_key] = agent
        visible_agents.append(agent)
    agent_ids = {str(item.agent_id) for item in visible_agents}

    merged_agents: list[dict[str, Any]] = []
    for agent in visible_agents:
        activity = activity_by_agent.get(
            agent.agent_id,
            {
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
        connected = bool(activity.get("connected", False))
        effective_status = effective_desktop_agent_status(agent, connected=connected, now=now)
        merged_agents.append(
            {
                **desktop_agent_to_dto(agent),
                "status": effective_status.value,
                "connected": connected,
                "connectionState": desktop_agent_connection_state(agent, connected=connected, now=now),
                "queuedCommandCount": int(activity.get("queuedCommandCount", 0)),
                "activeStreamCount": int(activity.get("activeStreamCount", 0)),
                "pendingProbeCount": int(activity.get("pendingProbeCount", 0)),
                "activeHlsJobCount": int(activity.get("activeHlsJobCount", 0)),
                "hlsJobCount": int(activity.get("hlsJobCount", 0)),
            }
        )

    binding_summary = {
        "desktopAgentProjectCount": 0,
        "boundOnlineProjectCount": 0,
        "boundOfflineProjectCount": 0,
        "serverFsProjectCount": 0,
        "supersededBindingCount": 0,
    }
    project_bindings: list[dict[str, Any]] = []
    for project in sorted(project_items, key=lambda item: (str(item.title).lower(), str(item.project_id))):
        project_id = str(project.project_id)
        binding = project_bindings_by_id[project_id]
        source_kind = getattr(binding.source_kind, "value", str(binding.source_kind))
        bound_agent_id = None if binding.desktop_agent_id is None else str(binding.desktop_agent_id)
        bound_agent = None if bound_agent_id is None else all_agents_by_id.get(bound_agent_id)
        connected = bool(activity_by_agent.get(bound_agent_id or "", {}).get("connected", False))
        effective_status = (
            None if bound_agent is None else effective_desktop_agent_status(bound_agent, connected=connected, now=now)
        )
        superseded_by_agent_id = None
        if bound_agent is not None:
            canonical_agent = canonical_agents_by_device.get(
                _desktop_agent_device_key(device_name=bound_agent.device_name, platform=bound_agent.platform)
            )
            if canonical_agent is not None and str(canonical_agent.agent_id) != str(bound_agent.agent_id):
                superseded_by_agent_id = str(canonical_agent.agent_id)
        binding_state = "UNBOUND"
        if source_kind == MaterialSourceKind.DESKTOP_AGENT_MANIFEST.value:
            binding_summary["desktopAgentProjectCount"] += 1
            if effective_status == DesktopAgentStatus.ONLINE:
                binding_summary["boundOnlineProjectCount"] += 1
                binding_state = "ONLINE"
            else:
                binding_summary["boundOfflineProjectCount"] += 1
                binding_state = "OFFLINE"
            if superseded_by_agent_id is not None:
                binding_summary["supersededBindingCount"] += 1
        else:
            binding_summary["serverFsProjectCount"] += 1
        project_bindings.append(
            {
                "projectId": project_id,
                "projectTitle": str(project.title),
                "sourceKind": source_kind,
                "desktopAgentId": bound_agent_id,
                "sourceRootLabel": binding.source_root_label,
                "deviceName": None if bound_agent is None else str(bound_agent.device_name),
                "appVersion": None if bound_agent is None else str(bound_agent.app_version),
                "lastSeenAt": None if bound_agent is None else str(bound_agent.last_seen_at),
                "pairedAt": None if bound_agent is None else str(bound_agent.paired_at),
                "connected": connected,
                "connectionState": None
                if bound_agent is None
                else desktop_agent_connection_state(bound_agent, connected=connected, now=now),
                "bindingState": binding_state,
                "supersededByAgentId": superseded_by_agent_id,
            }
        )

    sessions: list[MediaStreamSession] = []
    for project_id in project_ids:
        sessions.extend(auth_store.list_media_stream_sessions_for_project(project_id))
    sessions.sort(key=lambda item: (_coerce_utc_datetime(item.updated_at), item.stream_id), reverse=True)

    sessions_by_status: dict[str, int] = {}
    bytes_from_agent_total = 0
    bytes_to_viewer_total = 0
    active_session_count = 0
    issue_reason_counts: dict[str, int] = {}
    for item in sessions:
        sessions_by_status[item.status] = sessions_by_status.get(item.status, 0) + 1
        bytes_from_agent_total += int(item.bytes_from_agent)
        bytes_to_viewer_total += int(item.bytes_to_viewer)
        if item.status in {"OPENING", "STREAMING"}:
            active_session_count += 1
        if item.status in {"FAILED", "CANCELLED"}:
            _increment_counter(issue_reason_counts, str(item.failure_reason or "").strip() or "unknown")

    recent_issues = [
        _session_to_issue_dto(item, project_titles.get(item.project_id))
        for item in sessions
        if item.status in {"FAILED", "CANCELLED"}
    ][: max(1, int(recent_issue_limit))]

    runtime_hls_jobs_by_id: dict[str, dict[str, Any]] = {}
    for job in runtime.list_hls_jobs():
        if str(job.agent_id) not in agent_ids and str(job.project_id) not in project_id_set:
            continue
        runtime_hls_jobs_by_id[str(job.job_id)] = {
            "jobId": str(job.job_id),
            "cacheKey": str(job.cache_key),
            "agentId": str(job.agent_id),
            "projectId": str(job.project_id),
            "instanceId": str(job.instance_id),
            "relativePath": str(job.relative_path),
            "profile": dict(job.profile),
            "createdAt": str(job.created_at),
            "updatedAt": str(job.updated_at),
            "expiresAt": str(job.expires_at),
            "state": str(job.state),
            "message": None if job.message is None else str(job.message),
            "startedAt": job.started_at,
            "finishedAt": job.finished_at,
            "lastArtifactAt": job.last_artifact_at,
            "connectionLostAt": job.connection_lost_at,
            "artifactCount": int(job.artifact_count),
            "artifactBytes": int(job.artifact_bytes),
        }
    persisted_hls_jobs: list[dict[str, Any]] = []
    for project_id in project_ids:
        for item in auth_store.list_desktop_agent_hls_job_audits_for_project(project_id):
            dto = _hls_job_audit_to_dto(item)
            runtime_current = runtime_hls_jobs_by_id.get(str(dto.get("jobId", "")))
            if runtime_current is not None:
                dto.update(runtime_current)
            persisted_hls_jobs.append(dto)
    persisted_hls_job_ids = {str(item.get("jobId", "")) for item in persisted_hls_jobs}
    runtime_visible_jobs = [
        dict(item)
        for job_id, item in runtime_hls_jobs_by_id.items()
        if job_id not in persisted_hls_job_ids
    ]
    all_hls_jobs = persisted_hls_jobs + runtime_visible_jobs
    all_hls_jobs.sort(
        key=lambda item: (
            _coerce_utc_datetime(str(item.get("updatedAt") or item.get("createdAt") or "")),
            str(item.get("jobId", "")),
        ),
        reverse=True,
    )
    visible_hls_jobs = all_hls_jobs[: max(1, int(recent_hls_job_limit))]
    hls_jobs_by_state: dict[str, int] = {}
    hls_issue_reason_counts: dict[str, int] = {}
    activity_windows = {
        "lastHour": _empty_hls_window(),
        "lastDay": _empty_hls_window(),
    }
    last_hour_cutoff = now - timedelta(hours=1)
    last_day_cutoff = now - timedelta(days=1)
    for item in all_hls_jobs:
        state = str(item.get("state", "UNKNOWN"))
        _increment_counter(hls_jobs_by_state, state)
        reason = str(item.get("message", "") or "").strip()
        if state in {"FAILED", "CANCELLED"} and reason:
            _increment_counter(hls_issue_reason_counts, reason)
        event_time = _coerce_utc_datetime(str(item.get("updatedAt") or item.get("createdAt") or ""))
        artifact_bytes = int(item.get("artifactBytes", 0))
        if event_time >= last_hour_cutoff:
            _accumulate_hls_window(activity_windows["lastHour"], state=state, artifact_bytes=artifact_bytes)
        if event_time >= last_day_cutoff:
            _accumulate_hls_window(activity_windows["lastDay"], state=state, artifact_bytes=artifact_bytes)
    total_hls_job_count = len(all_hls_jobs)
    total_active_hls_job_count = sum(
        1 for item in all_hls_jobs if str(item.get("state", "")).strip().upper() not in {"COMPLETED", "FAILED", "CANCELLED"}
    )
    diagnostic_by_category: dict[str, int] = {}
    diagnostic_by_level: dict[str, int] = {}
    diagnostic_by_type: dict[str, int] = {}
    error_count = 0
    warning_count = 0
    alerts: list[dict[str, Any]] = []
    recent_error_cutoff = now - timedelta(hours=max(1, int(alert_since_hours)))
    aggregated_error_alerts: dict[tuple[str, str, str, str | None], dict[str, Any]] = {}
    for item in diagnostic_events:
        _increment_counter(diagnostic_by_category, item.category)
        _increment_counter(diagnostic_by_level, item.level)
        _increment_counter(diagnostic_by_type, item.event_type)
        normalized_level = str(item.level).strip().upper()
        if normalized_level == "ERROR":
            error_count += 1
        elif normalized_level == "WARNING":
            warning_count += 1
        if normalized_level not in {"ERROR", "WARNING"}:
            continue
        created_at = _coerce_utc_datetime(item.created_at)
        if created_at < recent_error_cutoff:
            continue
        key = (normalized_level, item.agent_id, item.event_type, item.project_id)
        current = aggregated_error_alerts.setdefault(
            key,
            {
                "severity": "error" if normalized_level == "ERROR" else "warning",
                "code": item.event_type,
                "title": f"{item.category}: {item.event_type}",
                "message": item.message,
                "agentId": item.agent_id,
                "projectId": item.project_id,
                "observedAt": item.created_at,
                "count": 0,
            },
        )
        current["count"] = int(current.get("count", 0)) + 1
        if created_at > _coerce_utc_datetime(str(current.get("observedAt"))):
            current["observedAt"] = item.created_at
            current["message"] = item.message
    alerts.extend(
        sorted(
            aggregated_error_alerts.values(),
            key=lambda item: (
                1 if str(item.get("severity")) == "error" else 0,
                _coerce_utc_datetime(str(item.get("observedAt", ""))).timestamp(),
            ),
            reverse=True,
        )[:8]
    )
    recent_diagnostics = [_diagnostic_event_to_dto(item) for item in diagnostic_events[: max(1, int(recent_diagnostic_limit))]]

    return {
        "available": True,
        "projectCount": len(project_ids),
        "projectIds": list(project_ids),
        "bindingSummary": binding_summary,
        "projectBindings": project_bindings,
        "agentCount": len(merged_agents),
        "agents": merged_agents,
        "streamSummary": {
            "sessionCount": len(sessions),
            "activeSessionCount": active_session_count,
            "failedSessionCount": sessions_by_status.get("FAILED", 0),
            "cancelledSessionCount": sessions_by_status.get("CANCELLED", 0),
            "completedSessionCount": sessions_by_status.get("COMPLETED", 0),
            "bytesFromAgentTotal": bytes_from_agent_total,
            "bytesToViewerTotal": bytes_to_viewer_total,
            "sessionsByStatus": dict(sorted(sessions_by_status.items())),
            "issueReasonCounts": dict(sorted(issue_reason_counts.items())),
        },
        "recentIssues": recent_issues,
        "hlsSummary": {
            "jobCount": total_hls_job_count,
            "activeHlsJobCount": total_active_hls_job_count,
            "jobsByState": dict(sorted(hls_jobs_by_state.items())),
            "issueReasonCounts": dict(sorted(hls_issue_reason_counts.items())),
            "activityWindows": activity_windows,
        },
        "recentHlsJobs": visible_hls_jobs,
        "diagnosticSummary": {
            "eventCount": len(diagnostic_events),
            "errorCount": error_count,
            "warningCount": warning_count,
            "eventsByCategory": dict(sorted(diagnostic_by_category.items())),
            "eventsByLevel": dict(sorted(diagnostic_by_level.items())),
            "eventsByType": dict(sorted(diagnostic_by_type.items())),
        },
        "recentDiagnostics": recent_diagnostics,
        "alerts": alerts,
        "trends": _build_relay_trends(
            trend_samples,
            sample_bucket_seconds=int(sampling_report.get("metricSampleBucketSeconds", sampling_config.bucket_seconds)),
            retention_days=int(sampling_report.get("metricSampleRetentionDays", sampling_config.retention_days)),
            now=now,
        ),
    }
