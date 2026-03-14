from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.models.desktop_agent_hls_job_audit import DesktopAgentHlsJobAudit
from backend.models.desktop_agent_metric_sample import DesktopAgentMetricSample
from backend.models.hls_cache_entry import HlsCacheEntry
from backend.models.media_stream_session import MediaStreamSession
from backend.system.auth_store import AuthStore


def _env_non_negative_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return max(0, value)


def _coerce_utc_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bucket_start(now: datetime, bucket_seconds: int) -> datetime:
    current = _coerce_utc_datetime(now)
    epoch_seconds = int(current.timestamp())
    bucket = (epoch_seconds // max(1, int(bucket_seconds))) * max(1, int(bucket_seconds))
    return datetime.fromtimestamp(bucket, tz=timezone.utc).replace(microsecond=0)


@dataclass(frozen=True, slots=True)
class DesktopAgentMetricSamplingConfig:
    bucket_seconds: int
    retention_days: int


def current_desktop_agent_metric_sampling_config() -> DesktopAgentMetricSamplingConfig:
    return DesktopAgentMetricSamplingConfig(
        bucket_seconds=_env_non_negative_int("PLM_AGENT_METRIC_SAMPLE_INTERVAL_SECONDS", 300),
        retention_days=max(1, _env_non_negative_int("PLM_AGENT_METRIC_SAMPLE_RETENTION_DAYS", 30)),
    )


def _empty_project_metrics() -> dict[str, int]:
    return {
        "session_count": 0,
        "active_stream_count": 0,
        "completed_stream_count": 0,
        "failed_stream_count": 0,
        "cancelled_stream_count": 0,
        "bytes_from_agent_total": 0,
        "bytes_to_viewer_total": 0,
        "hls_job_count": 0,
        "active_hls_job_count": 0,
        "completed_hls_job_count": 0,
        "failed_hls_job_count": 0,
        "cancelled_hls_job_count": 0,
        "hls_artifact_bytes_total": 0,
        "hls_cache_entry_count": 0,
        "hls_cache_bytes": 0,
    }


def _apply_stream_metrics(target: dict[str, int], item: MediaStreamSession) -> None:
    target["session_count"] += 1
    target["bytes_from_agent_total"] += max(0, int(item.bytes_from_agent))
    target["bytes_to_viewer_total"] += max(0, int(item.bytes_to_viewer))
    state = str(item.status or "").strip().upper()
    if state in {"OPENING", "STREAMING"}:
        target["active_stream_count"] += 1
    elif state == "COMPLETED":
        target["completed_stream_count"] += 1
    elif state == "FAILED":
        target["failed_stream_count"] += 1
    elif state == "CANCELLED":
        target["cancelled_stream_count"] += 1


def _apply_hls_job_metrics(target: dict[str, int], item: DesktopAgentHlsJobAudit) -> None:
    target["hls_job_count"] += 1
    target["hls_artifact_bytes_total"] += max(0, int(item.artifact_bytes))
    state = str(item.state or "").strip().upper()
    if state in {"OPENING", "RUNNING"}:
        target["active_hls_job_count"] += 1
    elif state == "COMPLETED":
        target["completed_hls_job_count"] += 1
    elif state == "FAILED":
        target["failed_hls_job_count"] += 1
    elif state == "CANCELLED":
        target["cancelled_hls_job_count"] += 1


def _apply_hls_cache_metrics(target: dict[str, int], item: HlsCacheEntry) -> None:
    target["hls_cache_entry_count"] += 1
    target["hls_cache_bytes"] += max(0, int(item.size_bytes))


def persist_desktop_agent_metric_samples(
    auth_store: AuthStore,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    config = current_desktop_agent_metric_sampling_config()
    observed_at = _coerce_utc_datetime(now or datetime.now(timezone.utc)).replace(microsecond=0)
    payload: dict[str, Any] = {
        "metricSampleBucketSeconds": int(config.bucket_seconds),
        "metricSampleRetentionDays": int(config.retention_days),
        "metricSampleCapturedAt": observed_at.isoformat(),
        "metricSampleBucketStart": None,
        "sampledMetricProjectCount": 0,
        "prunedMetricSampleCount": 0,
    }
    if config.bucket_seconds <= 0:
        return payload

    bucket_start = _bucket_start(observed_at, config.bucket_seconds)
    payload["metricSampleBucketStart"] = bucket_start.isoformat()
    metrics_by_project: dict[str, dict[str, int]] = {}

    for item in auth_store.list_all_media_stream_sessions():
        metrics = metrics_by_project.setdefault(str(item.project_id), _empty_project_metrics())
        _apply_stream_metrics(metrics, item)
    for item in auth_store.list_all_desktop_agent_hls_job_audits():
        metrics = metrics_by_project.setdefault(str(item.project_id), _empty_project_metrics())
        _apply_hls_job_metrics(metrics, item)
    for item in auth_store.list_all_hls_cache_entries():
        metrics = metrics_by_project.setdefault(str(item.project_id), _empty_project_metrics())
        _apply_hls_cache_metrics(metrics, item)

    for project_id, metrics in metrics_by_project.items():
        auth_store.upsert_desktop_agent_metric_sample(
            DesktopAgentMetricSample(
                project_id=str(project_id),
                bucket_start=bucket_start.isoformat(),
                bucket_seconds=int(config.bucket_seconds),
                captured_at=observed_at.isoformat(),
                session_count=int(metrics["session_count"]),
                active_stream_count=int(metrics["active_stream_count"]),
                completed_stream_count=int(metrics["completed_stream_count"]),
                failed_stream_count=int(metrics["failed_stream_count"]),
                cancelled_stream_count=int(metrics["cancelled_stream_count"]),
                bytes_from_agent_total=int(metrics["bytes_from_agent_total"]),
                bytes_to_viewer_total=int(metrics["bytes_to_viewer_total"]),
                hls_job_count=int(metrics["hls_job_count"]),
                active_hls_job_count=int(metrics["active_hls_job_count"]),
                completed_hls_job_count=int(metrics["completed_hls_job_count"]),
                failed_hls_job_count=int(metrics["failed_hls_job_count"]),
                cancelled_hls_job_count=int(metrics["cancelled_hls_job_count"]),
                hls_artifact_bytes_total=int(metrics["hls_artifact_bytes_total"]),
                hls_cache_entry_count=int(metrics["hls_cache_entry_count"]),
                hls_cache_bytes=int(metrics["hls_cache_bytes"]),
            )
        )

    prune_before = (observed_at - timedelta(days=int(config.retention_days))).replace(microsecond=0).isoformat()
    payload["sampledMetricProjectCount"] = len(metrics_by_project)
    payload["prunedMetricSampleCount"] = auth_store.delete_desktop_agent_metric_samples_before(prune_before)
    return payload
